"""
module_1/pipeline.py — Collection orchestration helpers.

Exposes:
  run_api_collection_pipeline(...)  — collect from a news API, preprocess, and store
  run_url_collection_pipeline(...)  — scrape a single URL, preprocess, and store
"""

from __future__ import annotations

from typing import List, Optional

from pymongo.database import Database

from module_1_scraping.news_collector import collect_articles
from module_1_scraping.preprocessing import build_clean_article
from module_1_scraping.scraper import scrape_article
from shared.database import store_article
from shared.logger import get_logger
from shared.models import CleanArticle

log = get_logger("pipeline")


def run_api_collection_pipeline(
    db: Database,
    provider: str = "newsapi",
    query: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Collect articles from a news API, preprocess each one, and store in MongoDB.
    Returns a summary dict with collected / stored / duplicates / errors counts.
    """
    log.info(
        "run_api_collection_pipeline: provider=%s query=%r page=%d",
        provider, query, page,
    )

    raw_articles = collect_articles(
        provider=provider,
        query=query,
        category=category,
        source=source,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )

    stored: List[CleanArticle] = []
    duplicates = 0
    errors: List[str] = []

    for raw in raw_articles:
        try:
            clean = build_clean_article(raw)
            _, is_new = store_article(db, clean)
            if is_new:
                stored.append(clean)
            else:
                duplicates += 1
        except Exception as exc:
            msg = f"Error processing {raw.url}: {exc}"
            log.error(msg)
            errors.append(msg)

    result = {
        "collected": len(raw_articles),
        "stored": len(stored),
        "duplicates": duplicates,
        "articles": stored,
        "errors": errors,
    }
    log.info(
        "pipeline done: collected=%d stored=%d dups=%d errors=%d",
        result["collected"], result["stored"], result["duplicates"], len(errors),
    )
    return result


def run_url_collection_pipeline(
    db: Database,
    url: str,
    use_playwright: bool = False,
) -> tuple[CleanArticle, bool]:
    """
    Scrape a single URL, preprocess the content, and store it in MongoDB.
    Returns (clean_article, is_new).
    """
    log.info("run_url_collection_pipeline: url=%s playwright=%s", url, use_playwright)
    raw = scrape_article(url, use_playwright=use_playwright)
    clean = build_clean_article(raw)
    _, is_new = store_article(db, clean)
    msg = "Article stored." if is_new else "Duplicate — article already in database."
    log.info("url pipeline: %s  article_id=%s", msg, clean.article_id)
    return clean, is_new
