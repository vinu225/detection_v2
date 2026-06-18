"""
shared/utils.py — Shared utility functions used across all modules.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from typing import Optional
from urllib.parse import urlparse


def sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_article_id(url: str) -> str:
    """Generate a deterministic UUID v5 from a URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def extract_domain(url: str) -> str:
    """Return the bare domain (without www.) from a URL."""
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def validate_url(url: str) -> None:
    """Raise ValueError if the URL scheme is not http/https or has no hostname."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"URL has no hostname: {url}")


def normalize_text(text: str) -> str:
    """
    Unicode-normalize, replace smart quotes, and collapse whitespace.
    Newlines are preserved for downstream paragraph splitting.
    """
    text = unicodedata.normalize("NFKC", text)

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

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def jaccard(a: set, b: set) -> float:
    """Token-level Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0
