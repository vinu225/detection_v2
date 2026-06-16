"""
preprocessor.py — HTML cleaning, text normalization, and structured article generation.

Pipeline:
  raw HTML / text
      → strip noise (scripts, ads, nav, footer …)
      → normalize unicode, quotes, whitespace
      → split into paragraphs
      → deduplicate paragraphs
      → generate content_hash / url_hash
      → emit CleanArticle
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, Comment

from logger import get_logger
from models import CleanArticle, RawArticle

log = get_logger("preprocessor")

# ─────────────────────────────────────────────────────────────────────────────
# Tags / selectors that are always noise
# ─────────────────────────────────────────────────────────────────────────────
_NOISE_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "head", "meta", "link", "button", "form", "input", "select",
    "textarea", "label",
]

_NOISE_SELECTORS = [
    # navigation
    "nav", "header", "footer", "[role='navigation']", "[role='banner']",
    "[role='contentinfo']", ".nav", ".navbar", ".navigation",
    # ads
    ".ad", ".ads", ".advertisement", ".advert", "#ad", "#ads",
    "[class*='sponsor']", "[id*='sponsor']", "[class*='promo']",
    # social / sharing
    ".share", ".sharing", ".social", "[class*='share-']", "[class*='social-']",
    # cookies / GDPR
    ".cookie", ".cookie-banner", "#cookie-notice", "[class*='cookie']",
    # sidebars / related
    ".sidebar", ".related", ".recommended", ".widget",
    # comments
    "#comments", ".comments", "[class*='comment']",
    # newsletter / subscription
    ".newsletter", ".subscribe", "[class*='newsletter']",
    # paywall overlays
    ".paywall", "[class*='paywall']",
]

_MIN_PARAGRAPH_WORDS = 8   # paragraphs shorter than this are discarded
_MAX_DUPLICATE_RATIO = 0.8  # jaccard ratio above which a paragraph is a dup


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

    soup = _parse_and_strip(html)
    raw_text = soup.get_text(separator="\n")
    normalized = _normalize_text(raw_text)
    paragraphs = _extract_paragraphs(normalized)
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

    content_hash = _sha256(clean_text)
    url_hash = _sha256(raw.url)
    article_id = str(uuid.uuid5(uuid.NAMESPACE_URL, raw.url))

    return CleanArticle(
        article_id=article_id,
        title=_normalize_text(raw.title),
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


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_and_strip(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove noisy tags
    for tag in _NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    # Remove noisy selectors
    for selector in _NOISE_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            pass  # malformed selector — skip

    return soup


def _normalize_text(text: str) -> str:
    """Unicode normalize, fix smart quotes, collapse whitespace."""
    # NFKC normalization (e.g. ligatures → ascii)
    text = unicodedata.normalize("NFKC", text)

    # Smart / curly quotes → straight
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u00a0": " ",   # non-breaking space
        "\u200b": "",    # zero-width space
        "\u2026": "...", # ellipsis
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Collapse multiple spaces (but preserve newlines for paragraph splitting)
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines into double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def _extract_paragraphs(text: str) -> List[str]:
    """Split on blank lines, filter short / duplicate paragraphs."""
    raw_paras = [p.strip() for p in re.split(r"\n{2,}", text)]
    seen_tokens: List[set] = []
    result: List[str] = []

    for para in raw_paras:
        # Drop very short paragraphs (likely navigation cruft)
        if len(para.split()) < _MIN_PARAGRAPH_WORDS:
            continue
        # Deduplicate using token-level Jaccard similarity
        tokens = set(para.lower().split())
        is_dup = any(
            _jaccard(tokens, seen) >= _MAX_DUPLICATE_RATIO
            for seen in seen_tokens
        )
        if is_dup:
            continue
        seen_tokens.append(tokens)
        result.append(para)

    return result


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
