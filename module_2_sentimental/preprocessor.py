"""
module_2/preprocessor.py — Text normalization, URL removal, and special character handling for news articles.
"""

import re
import unicodedata
import logging
from typing import Optional

logger = logging.getLogger("sentiment_module.preprocessor")

# Regex to match URLs (http, https, ftp, www)
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+|ftp://\S+")

# Regex to match excessive punctuation (e.g., repeating !!! or ??? or ...)
EXCESSIVE_PUNC_PATTERN = re.compile(r"([!?,.:;])\1+")

# Characters to keep: alphanumeric, whitespace, standard punctuations, and common currency/math/text symbols.
# We strip emojis, control characters, and exotic/unrecognized Unicode blocks.
INVALID_CHARS_PATTERN = re.compile(r"[^\w\s.,!?;:'\"()\-\[\]$€£¥%@#&*+=/\\°%<>]")

def clean_text(text: Optional[str]) -> str:
    """
    Cleans raw text data for downstream RoBERTa sentiment analysis.
    Normalizes unicode, standardizes quotes, removes URLs and invalid chars,
    and formats whitespace.
    """
    if not text:
        return ""

    # 1. Unicode normalization (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # 2. Standardize smart quotes and other unicode anomalies
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u00a0": " ",   # non-breaking space
        "\u200b": "",    # zero-width space
        "\u2026": "...", # ellipsis
        "\u200e": "",    # Left-to-Right Mark
        "\u200f": "",    # Right-to-Left Mark
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # 3. Strip control characters
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")

    # 4. Remove URLs
    text = URL_PATTERN.sub("", text)

    # 5. Remove invalid/unsupported characters (e.g. emojis, exotic scripts, decorative chars)
    text = INVALID_CHARS_PATTERN.sub("", text)

    # 6. Collapse excessive punctuation (e.g., "!!!" -> "!", "???" -> "?")
    def punc_replacer(match):
        char = match.group(1)
        # Preserve triple dot ellipsis "..."
        if char == "." and len(match.group(0)) >= 3:
            return "..."
        return char

    text = EXCESSIVE_PUNC_PATTERN.sub(punc_replacer, text)

    # 7. Clean up whitespace
    # Replace multiple horizontal spaces/tabs with single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines into exactly two (representing paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing/leading spaces on individual lines
    text = "\n".join(line.strip() for line in text.splitlines())
    
    cleaned = text.strip()
    return cleaned
