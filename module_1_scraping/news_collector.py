"""
module_1/news_collector.py — Collect articles from:
  • NewsAPI   (https://newsapi.org)
  • GNews API (https://gnews.io)
  • RSS feeds (via feedparser)

All sources produce List[RawArticle] which the preprocessor then cleans.
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import datetime
from typing import List, Optional

import feedparser
import requests

from module_1_scraping.config import get_settings
from shared.logger import get_logger
from shared.models import RawArticle
from shared.constants import NEWSAPI_CATEGORIES, GNEWS_CATEGORIES

log = get_logger("news_collector")
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Shared session
# ─────────────────────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({"User-Agent": "NewsPipelineBot/1.0 (+https://example.com)"})


# ─────────────────────────────────────────────────────────────────────────────
# NewsAPI
# ─────────────────────────────────────────────────────────────────────────────

NEWSAPI_EVERYTHING = "https://newsapi.org/v2/everything"
NEWSAPI_TOP = "https://newsapi.org/v2/top-headlines"


def collect_from_newsapi(
    query: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> List[RawArticle]:
    """
    Fetch articles from NewsAPI.
    Uses /top-headlines when category/source is given, /everything otherwise.
    """
    api_key = settings.news_api_key
    if not api_key or "your_newsapi_key" in api_key:
        log.warning("NEWS_API_KEY not set or placeholder — skipping NewsAPI collection.")
        return []

    use_top = bool(category or source)
    endpoint = NEWSAPI_TOP if use_top else NEWSAPI_EVERYTHING

    params: dict = {
        "apiKey": api_key,
        "pageSize": min(page_size, 100),
        "page": page,
        "language": "en",
    }
    if query:
        params["q"] = query
    if category and category in NEWSAPI_CATEGORIES:
        params["category"] = category
    if source:
        params["sources"] = source
    if from_date and not use_top:
        params["from"] = from_date
    if to_date and not use_top:
        params["to"] = to_date

    log.info("NewsAPI request: endpoint=%s params=%s", endpoint, {k: v for k, v in params.items() if k != "apiKey"})

    try:
        resp = _session.get(endpoint, params=params, timeout=settings.scraper_timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.error("NewsAPI request failed: %s", exc)
        return []

    if data.get("status") != "ok":
        log.error("NewsAPI error: %s", data.get("message", "unknown"))
        return []

    articles = []
    for item in data.get("articles", []):
        try:
            articles.append(
                RawArticle(
                    title=item.get("title") or "Untitled",
                    author=item.get("author"),
                    source=item.get("source", {}).get("name"),
                    published_at=item.get("publishedAt"),
                    url=item["url"],
                    content=item.get("content"),
                    description=item.get("description"),
                )
            )
        except Exception as exc:
            log.warning("Skipping malformed NewsAPI item: %s", exc)

    log.info("NewsAPI returned %d articles (total results: %s)", len(articles), data.get("totalResults"))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# GNews API
# ─────────────────────────────────────────────────────────────────────────────

GNEWS_SEARCH = "https://gnews.io/api/v4/search"
GNEWS_TOP = "https://gnews.io/api/v4/top-headlines"


def collect_from_gnews(
    query: Optional[str] = None,
    category: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> List[RawArticle]:
    """Fetch articles from GNews API."""
    api_key = settings.gnews_api_key
    if not api_key or "your_gnews_key" in api_key:
        log.warning("GNEWS_API_KEY not set or placeholder — skipping GNews collection.")
        return []

    endpoint = GNEWS_TOP if (category and not query) else GNEWS_SEARCH

    params: dict = {
        "token": api_key,
        "lang": "en",
        "max": min(page_size, 10),   # GNews free tier: max 10
        "page": page,
    }
    if query:
        params["q"] = query
    if category and category in GNEWS_CATEGORIES:
        params["topic"] = category
    if from_date:
        params["from"] = _to_gnews_date(from_date)
    if to_date:
        params["to"] = _to_gnews_date(to_date)

    log.info("GNews request: endpoint=%s", endpoint)

    try:
        resp = _session.get(endpoint, params=params, timeout=settings.scraper_timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.error("GNews request failed: %s", exc)
        return []

    if "errors" in data:
        log.error("GNews API error: %s", data["errors"])
        return []

    articles = []
    for item in data.get("articles", []):
        try:
            articles.append(
                RawArticle(
                    title=item.get("title") or "Untitled",
                    author=item.get("source", {}).get("name"),
                    source=item.get("source", {}).get("name"),
                    published_at=item.get("publishedAt"),
                    url=item["url"],
                    content=item.get("content"),
                    description=item.get("description"),
                )
            )
        except Exception as exc:
            log.warning("Skipping malformed GNews item: %s", exc)

    log.info("GNews returned %d articles", len(articles))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# RSS Feeds
# ─────────────────────────────────────────────────────────────────────────────

def collect_from_rss(
    feed_urls: Optional[List[str]] = None,
    query: Optional[str] = None,
    max_per_feed: int = 20,
) -> List[RawArticle]:
    """
    Parse one or more RSS/Atom feeds.
    If `query` is given, only entries whose title or summary contain the query
    keyword (case-insensitive) are returned.
    """
    urls = feed_urls or settings.rss_feed_list
    if not urls:
        log.warning("No RSS feed URLs configured or provided.")
        return []

    articles: List[RawArticle] = []
    query_lower = query.lower() if query else None

    for url in urls:
        log.info("Parsing RSS feed: %s", url)
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            log.error("RSS parse error for %s: %s", url, exc)
            continue

        if feed.bozo and feed.bozo_exception:
            log.warning("Feed %s has bozo exception: %s", url, feed.bozo_exception)

        feed_title = feed.feed.get("title", url)
        count = 0

        for entry in feed.entries:
            if count >= max_per_feed:
                break

            title = entry.get("title", "Untitled")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")

            if not link:
                continue

            # Keyword filter
            if query_lower:
                haystack = (title + " " + summary).lower()
                if query_lower not in haystack:
                    continue

            published_at = _rss_date(entry)
            content = _rss_content(entry) or summary

            try:
                articles.append(
                    RawArticle(
                        title=title,
                        author=entry.get("author"),
                        source=feed_title,
                        published_at=published_at,
                        url=link,
                        content=content,
                        description=summary,
                    )
                )
                count += 1
            except Exception as exc:
                log.warning("Skipping bad RSS entry: %s", exc)

        log.info("RSS %s → %d articles", url, count)
        time.sleep(0.2)   # be polite

    log.info("RSS total collected: %d", len(articles))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Search scraping via DuckDuckGo HTML interface
# ─────────────────────────────────────────────────────────────────────────────

def collect_from_search(
    query: str,
    page_size: int = 5,
) -> List[RawArticle]:
    """
    Query DuckDuckGo HTML search interface to scrape web search results for the given query.
    Falls back to simple snippet content if page scraping fails or is blocked.
    """
    if not query:
        return []

    log.info("Collecting from web search scraping: query=%r limit=%d", query, page_size)
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = _session.get(url, headers=headers, timeout=settings.scraper_timeout)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        log.error("DuckDuckGo search request failed: %s", exc)
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    results = soup.find_all("div", class_="result")

    articles: List[RawArticle] = []
    count = 0

    for res in results:
        if count >= page_size:
            break

        title_el = res.find("a", class_="result__a")
        snippet_el = res.find("a", class_="result__snippet")
        
        if not title_el:
            continue

        raw_title = title_el.text.strip()
        snippet = snippet_el.text.strip() if snippet_el else ""
        href = title_el.get("href", "")

        # Decode the target URL from the ddg redirect link (uddg parameter)
        target_url = None
        if href:
            try:
                parsed = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed.query)
                target_url = params.get("uddg", [None])[0]
            except Exception as exc:
                log.warning("Failed to parse result URL %s: %s", href, exc)

        if not target_url:
            # Fall back to using the href directly or skip
            if href.startswith("http"):
                target_url = href
            else:
                continue

        # Try to scrape the full article body using scrape_article waterfall
        content = ""
        source = urllib.parse.urlparse(target_url).netloc or "Web Search"
        
        domain_lower = source.lower()
        is_social = any(s in domain_lower for s in ("reddit.com", "twitter.com", "x.com", "instagram.com", "facebook.com"))

        if not is_social:
            try:
                from module_1_scraping.scraper import scrape_article
                log.debug("Attempting to scrape full page content for: %s", target_url)
                scraped = scrape_article(target_url)
                content = scraped.content or ""
            except Exception as exc:
                log.warning("Failed to scrape full content for %s: %s. Using snippet fallback.", target_url, exc)

        # If full page scraping failed or is social media, fall back to snippet
        if not content.strip():
            content = snippet or f"Live update from {source} regarding: {query}."

        try:
            articles.append(
                RawArticle(
                    title=raw_title,
                    author=source,
                    source=source,
                    published_at=datetime.utcnow().isoformat() + "Z",
                    url=target_url,
                    content=content,
                    description=snippet,
                )
            )
            count += 1
        except Exception as exc:
            log.warning("Skipping bad search item: %s", exc)

    log.info("Web search returned %d articles", len(articles))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Batch helper
# ─────────────────────────────────────────────────────────────────────────────

def collect_articles(
    provider: str = "newsapi",
    query: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> List[RawArticle]:
    """
    Unified entry point — dispatches to the correct provider.
    """
    log.info(
        "collect_articles: provider=%s query=%r category=%r page=%d",
        provider, query, category, page,
    )

    if provider == "newsapi":
        return collect_from_newsapi(
            query=query, category=category, source=source,
            from_date=from_date, to_date=to_date,
            page=page, page_size=page_size,
        )
    elif provider == "gnews":
        return collect_from_gnews(
            query=query, category=category,
            from_date=from_date, to_date=to_date,
            page=page, page_size=page_size,
        )
    elif provider == "rss":
        return collect_from_rss(query=query, max_per_feed=page_size)
    elif provider == "search":
        return collect_from_search(query=query, page_size=page_size)
    else:
        log.error("Unknown provider: %s", provider)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _to_gnews_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to GNews format YYYY-MM-DDTHH:MM:SSZ."""
    try:
        dt = datetime.fromisoformat(iso_date.split("T")[0])
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return iso_date


def _rss_date(entry) -> Optional[str]:
    """Extract publication date from an RSS entry."""
    for field in ("published", "updated", "created"):
        val = entry.get(field)
        if val:
            return val
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            try:
                return datetime(*val[:6]).isoformat()
            except Exception:
                pass
    return None


def _rss_content(entry) -> Optional[str]:
    """Extract full content from RSS entry content block."""
    content_list = entry.get("content", [])
    if content_list:
        return content_list[0].get("value", "")
    return None
