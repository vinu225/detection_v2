"""
module_1/html_cleaner.py — Noise-tag removal and HTML comment stripping.

Responsible for:
  - Removing script, style, nav, footer, ads, and other boilerplate elements
  - Stripping HTML comments
  - Returning a cleaned BeautifulSoup tree for downstream text extraction
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Comment

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


def parse_and_strip(html: str) -> BeautifulSoup:
    """
    Parse raw HTML with lxml, strip all known noise tags and selectors,
    and return the cleaned BeautifulSoup tree.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove noisy tags
    for tag in _NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    # Remove noisy CSS selectors
    for selector in _NOISE_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            pass  # malformed selector — skip

    return soup
