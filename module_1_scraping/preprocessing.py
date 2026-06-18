"""
module_1/preprocessing.py — Main preprocessing dispatcher.

Public API:
  clean_html(html, base_url)        → (clean_text, paragraphs)
  build_clean_article(raw, html)    → CleanArticle

Aggregates html_cleaner and content_extractor; exposes the same interface
as the original root preprocessor.py for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from module_1_scraping.html_cleaner import parse_and_strip
from module_1_scraping.content_extractor import extract_paragraphs
from shared.logger import get_logger
from shared.models import CleanArticle, RawArticle
from shared.utils import normalize_text, sha256, make_article_id

log = get_logger("preprocessing")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def clean_html(html: str, base_url: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Strip noise from raw HTML and return (clean_text, paragraphs).
    Works even when `html` is already plain text (no-op on non-HTML).
    """
    if not html:
        return "", []

    soup = parse_and_strip(html)
    raw_text = soup.get_text(separator="\n")
    normalized = normalize_text(raw_text)
    paragraphs = extract_paragraphs(normalized)
    clean_text = "\n\n".join(paragraphs)

    log.debug(
        "clean_html: %d chars in → %d paragraphs, %d chars out",
        len(html), len(paragraphs), len(clean_text),
    )
    return clean_text, paragraphs


def build_clean_article(
    raw: RawArticle,
    scraped_html: Optional[str] = None,
) -> CleanArticle:
    """
    Convert a RawArticle (+ optional scraped HTML) into a CleanArticle.
    If scraped_html is provided it takes priority over raw.content.
    """
    source_text = scraped_html or raw.content or raw.description or ""
    clean_text, paragraphs = clean_html(source_text)

    # Fall back to description if body is empty
    if not clean_text and raw.description:
        clean_text, paragraphs = clean_html(raw.description)

    content_hash = sha256(clean_text)
    url_hash = sha256(raw.url)
    article_id = make_article_id(raw.url)

    return CleanArticle(
        article_id=article_id,
        title=normalize_text(raw.title),
        author=raw.author,
        source=raw.source,
        publication_date=raw.published_at,
        url=raw.url,
        clean_text=clean_text,
        word_count=len(clean_text.split()),
        paragraphs=paragraphs,
        content_hash=content_hash,
        url_hash=url_hash,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )
