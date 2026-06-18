"""
module_2/html_loader.py — HTML extraction, noise removal, and metadata gathering for news articles.
"""

import logging
from pathlib import Path
from typing import Dict, Union, Optional
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger("sentiment_module.html_loader")

_NOISE_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "head", "meta", "link", "button", "form", "input", "select",
    "textarea", "label",
]

_NOISE_SELECTORS = [
    "nav", "header", "footer", "[role='navigation']", "[role='banner']",
    "[role='contentinfo']", ".nav", ".navbar", ".navigation",
    ".ad", ".ads", ".advertisement", ".advert", "#ad", "#ads",
    "[class*='sponsor']", "[id*='sponsor']", "[class*='promo']",
    ".share", ".sharing", ".social", "[class*='share-']", "[class*='social-']",
    ".cookie", ".cookie-banner", "#cookie-notice", "[class*='cookie']",
    ".sidebar", ".related", ".recommended", ".widget",
    "#comments", ".comments", "[class*='comment']",
    ".newsletter", ".subscribe", "[class*='newsletter']",
    ".paywall", "[class*='paywall']",
]

def clean_html_content(html_str: str) -> Dict[str, str]:
    """
    Parses HTML content, extracts the title, body text, and any meta tags.
    Robust against corrupted HTML and missing components.
    """
    result = {
        "title": "",
        "content": "",
        "source": "",
        "author": "",
        "url": "",
        "publication_date": ""
    }
    
    if not html_str or not isinstance(html_str, str):
        return result

    # Fallback parsing strategy for robust error handling
    soup = None
    for parser in ["lxml", "html.parser"]:
        try:
            soup = BeautifulSoup(html_str, parser)
            break
        except Exception as e:
            logger.warning(f"Failed to parse HTML using parser {parser}: {e}")
            
    if soup is None:
        logger.error("All HTML parsers failed. Returning empty dict.")
        return result

    # 1. Gather metadata from meta tags BEFORE decomposing them
    # Author
    meta_author = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", attrs={"property": "article:author"})
    if meta_author:
        result["author"] = meta_author.get("content", "").strip()
        
    # Publication Date
    meta_date = (
        soup.find("meta", attrs={"name": "publication_date"}) or 
        soup.find("meta", attrs={"property": "article:published_time"}) or
        soup.find("meta", attrs={"name": "date"})
    )
    if meta_date:
        result["publication_date"] = meta_date.get("content", "").strip()
        
    # Source / Site Name
    meta_source = soup.find("meta", attrs={"property": "og:site_name"})
    if meta_source:
        result["source"] = meta_source.get("content", "").strip()
        
    # Canonical URL
    meta_url = soup.find("link", rel="canonical") or soup.find("meta", attrs={"property": "og:url"})
    if meta_url:
        result["url"] = (meta_url.get("href") or meta_url.get("content") or "").strip()

    # 2. Extract Title
    title = ""
    # Check h1 tags first, but ignore if nested in head/title (unclosed tags artifact)
    h1_tag = soup.find("h1")
    if h1_tag and not (h1_tag.find_parent("head") or h1_tag.find_parent("title")):
        title = h1_tag.get_text(strip=True)
    
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
    result["title"] = title

    # 3. Strip HTML Comments
    try:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    except Exception as e:
        logger.debug(f"Error extracting comments: {e}")

    # 4. Decompose noisy elements
    for tag in _NOISE_TAGS:
        try:
            for el in soup.find_all(tag):
                el.decompose()
        except Exception as e:
            logger.debug(f"Error decomposing tag {tag}: {e}")

    for selector in _NOISE_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception as e:
            logger.debug(f"Error decomposing selector {selector}: {e}")

    # 5. Extract Content Text
    body_tag = soup.find("body")
    target_node = body_tag if body_tag else soup
    
    try:
        content_text = target_node.get_text(separator="\n")
    except Exception as e:
        logger.error(f"Error generating text from remaining soup: {e}")
        content_text = ""
        
    result["content"] = content_text
    
    return result

def load_html_file(file_path: Union[str, Path]) -> Dict[str, str]:
    """
    Loads an HTML file and extracts title, content, and metadata.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.error(f"HTML file not found: {path}")
        raise FileNotFoundError(f"HTML file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
    except Exception as e:
        logger.error(f"Error reading HTML file {path}: {e}")
        raise ValueError(f"Failed to read HTML file: {e}")

    result = clean_html_content(html_content)
    logger.info(f"Successfully loaded and cleaned HTML from {path}")
    return result
