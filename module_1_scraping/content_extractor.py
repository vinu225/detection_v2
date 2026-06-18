"""
module_1/content_extractor.py — Paragraph extraction, normalization, and deduplication.

Responsible for:
  - Splitting cleaned text into paragraphs
  - Filtering short paragraphs
  - Deduplicating near-identical paragraphs via Jaccard similarity
"""

from __future__ import annotations

import re
from typing import List

from shared.utils import jaccard, normalize_text
from shared.constants import MIN_PARAGRAPH_WORDS, MAX_DUPLICATE_RATIO


def extract_paragraphs(text: str) -> List[str]:
    """
    Split normalized text on blank lines, then filter short and near-duplicate
    paragraphs using token-level Jaccard similarity.
    """
    raw_paras = [p.strip() for p in re.split(r"\n{2,}", text)]
    seen_tokens: List[set] = []
    result: List[str] = []

    for para in raw_paras:
        # Drop very short paragraphs (likely navigation cruft)
        if len(para.split()) < MIN_PARAGRAPH_WORDS:
            continue
        # Deduplicate using token-level Jaccard similarity
        tokens = set(para.lower().split())
        is_dup = any(
            jaccard(tokens, seen) >= MAX_DUPLICATE_RATIO
            for seen in seen_tokens
        )
        if is_dup:
            continue
        seen_tokens.append(tokens)
        result.append(para)

    return result
