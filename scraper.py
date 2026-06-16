"""
scraper.py — Fetch full article content from arbitrary URLs.

Strategy (waterfall):
  1. requests + BeautifulSoup  — fast, works for ~80 % of sites
  2. LangChain WebBaseLoader   — fallback with more robust parsing
  3. LangChain PlaywrightURLLoader — JS-rendered sites (opt-in or auto-fallback)

Each strategy returns a RawArticle.  The caller decides which strategy to use
via the `use_playwright` flag; this module will auto-fall-back internally if
simple scraping yields too little content.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import get_settings
from logger import get_logger
from models import RawArticle

log = get_logger("scraper")
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_MIN_CONTENT_LENGTH = 200   # below this, try a richer strategy
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def scrape_article(url: str, use_playwright: bool = False) -> RawArticle:
    """
    Scrape and return a RawArticle for `url`.
    Raises ValueError for invalid URLs, RuntimeError for unrecoverable failures.
    """
    _validate_url(url)
    log.info("Scraping URL: %s (playwright=%s)", url, use_playwright)

    if use_playwright:
        return _scrape_playwright(url)

    # Try fast path first
    article = _scrape_requests(url)
    if len(article.content or "") >= _MIN_CONTENT_LENGTH:
        return article

    log.info("Content too short (%d chars), trying WebBaseLoader…", len(article.content or ""))

    # Fallback to LangChain WebBaseLoader
    try:
        article = _scrape_webbaseloader(url)
        if len(article.content or "") >= _MIN_CONTENT_LENGTH:
            return article
    except Exception as exc:
        log.warning("WebBaseLoader failed: %s", exc)

    # Final fallback — Playwright
    log.info("Falling back to Playwright for %s", url)
    try:
        return _scrape_playwright(url)
    except Exception as exc:
        log.error("All scraping strategies failed for %s: %s", url, exc)
        # Return what we have rather than raising
        if article.content:
            return article
        raise RuntimeError(f"Could not scrape {url}: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: requests + BeautifulSoup
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_requests(url: str) -> RawArticle:
    retries = settings.scraper_max_retries
    delay = settings.scraper_rate_limit_delay

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers=_DEFAULT_HEADERS,
                timeout=settings.scraper_timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
            final_url = resp.url
            html = resp.text
            break
        except requests.Timeout:
            log.warning("Timeout on attempt %d/%d for %s", attempt, retries, url)
            if attempt == retries:
                raise RuntimeError(f"Request timed out after {retries} attempts: {url}")
            time.sleep(delay * attempt)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else 0
            if status == 429:
                wait = delay * (2 ** attempt)
                log.warning("Rate-limited (429) — waiting %.1fs before retry", wait)
                time.sleep(wait)
                if attempt == retries:
                    raise RuntimeError(f"Rate-limited after {retries} attempts: {url}")
            else:
                raise RuntimeError(f"HTTP {status} for {url}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Request error for {url}: {exc}") from exc

    return _parse_html(html, final_url)


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: LangChain WebBaseLoader
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_webbaseloader(url: str) -> RawArticle:
    try:
        from langchain_community.document_loaders import WebBaseLoader
    except ImportError:
        raise RuntimeError("langchain-community not installed")

    loader = WebBaseLoader(url)
    loader.requests_kwargs = {"timeout": settings.scraper_timeout, "headers": _DEFAULT_HEADERS}
    docs = loader.load()

    if not docs:
        raise RuntimeError("WebBaseLoader returned no documents")

    doc = docs[0]
    content = doc.page_content or ""
    metadata = doc.metadata or {}

    return RawArticle(
        title=metadata.get("title", _extract_domain(url)),
        author=metadata.get("author"),
        source=_extract_domain(url),
        published_at=metadata.get("date"),
        url=url,
        content=content,
        description=metadata.get("description"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: Playwright (JS rendering)
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_playwright(url: str) -> RawArticle:
    try:
        from langchain_community.document_loaders import PlaywrightURLLoader
    except ImportError:
        raise RuntimeError("langchain-community or playwright not installed")

    loader = PlaywrightURLLoader(
        urls=[url],
        remove_selectors=["nav", "footer", "header", ".ad", ".ads", "script", "style"],
    )

    try:
        docs = loader.load()
    except Exception as exc:
        raise RuntimeError(f"Playwright scrape failed: {exc}") from exc

    if not docs:
        raise RuntimeError("PlaywrightURLLoader returned no documents")

    doc = docs[0]
    return RawArticle(
        title=doc.metadata.get("title", _extract_domain(url)),
        author=doc.metadata.get("author"),
        source=_extract_domain(url),
        published_at=doc.metadata.get("date"),
        url=url,
        content=doc.page_content,
        description=doc.metadata.get("description"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTML parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_html(html: str, url: str) -> RawArticle:
    """Parse HTML with BeautifulSoup and extract article metadata + body."""
    soup = BeautifulSoup(html, "lxml")

    title = _extract_title(soup)
    author = _extract_author(soup)
    published_at = _extract_date(soup)
    description = _extract_meta(soup, ["description", "og:description", "twitter:description"])
    content = _extract_body(soup)

    return RawArticle(
        title=title or _extract_domain(url),
        author=author,
        source=_extract_domain(url),
        published_at=published_at,
        url=url,
        content=content,
        description=description,
    )


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    for selector in [
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
        "h1",
        "title",
    ]:
        el = soup.select_one(selector)
        if el:
            return (el.get("content") or el.get_text()).strip()
    return None


def _extract_author(soup: BeautifulSoup) -> Optional[str]:
    for selector in [
        'meta[name="author"]',
        'meta[property="article:author"]',
        '[rel="author"]',
        ".author",
        '[class*="byline"]',
        '[itemprop="author"]',
    ]:
        el = soup.select_one(selector)
        if el:
            val = el.get("content") or el.get_text()
            if val:
                return val.strip()
    return None


def _extract_date(soup: BeautifulSoup) -> Optional[str]:
    for selector in [
        'meta[property="article:published_time"]',
        'meta[name="date"]',
        'meta[name="pubdate"]',
        'time[datetime]',
        '[itemprop="datePublished"]',
    ]:
        el = soup.select_one(selector)
        if el:
            val = el.get("content") or el.get("datetime") or el.get_text()
            if val:
                return val.strip()
    return None


def _extract_meta(soup: BeautifulSoup, names: list) -> Optional[str]:
    for name in names:
        el = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if el and el.get("content"):
            return el["content"].strip()
    return None


def _extract_body(soup: BeautifulSoup) -> str:
    """Find the main article body with a priority cascade."""
    for selector in [
        "article",
        '[role="main"]',
        "main",
        '[itemprop="articleBody"]',
        ".article-body",
        ".post-content",
        ".entry-content",
        ".story-body",
        ".article-content",
        "#content",
        ".content",
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator="\n")

    # Last resort: body
    body = soup.find("body")
    return body.get_text(separator="\n") if body else soup.get_text(separator="\n")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"URL has no hostname: {url}")


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url
