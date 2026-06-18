"""
module_2/tests/test_html_loader.py — Unit tests for html_loader.py.
"""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from module_2_sentimental.html_loader import clean_html_content, load_html_file

def test_clean_html_content_basic():
    html = """
    <html>
      <head>
        <title>HTML Article Title</title>
      </head>
      <body>
        <h1>Main Heading Title</h1>
        <p>This is the actual article content that we want to extract.</p>
      </body>
    </html>
    """
    res = clean_html_content(html)
    assert res["title"] == "Main Heading Title"
    assert "actual article content" in res["content"]

def test_clean_html_content_noise_removal():
    html = """
    <html>
      <head>
        <title>Page Title</title>
        <style>body { color: red; }</style>
      </head>
      <body>
        <nav>
          <a href="/home">Home</a> | <a href="/about">About</a>
        </nav>
        <div class="ad">
          <p>Buy our products now!</p>
        </div>
        <script>console.log("noisy script");</script>
        <h1>Article Headline</h1>
        <p>This is real content.</p>
        <footer>
          <p>&copy; 2026 Corporation</p>
        </footer>
      </body>
    </html>
    """
    res = clean_html_content(html)
    assert res["title"] == "Article Headline"
    # Content should keep the paragraph but drop style, nav, ads, scripts, footer
    content = res["content"]
    assert "This is real content." in content
    assert "Buy our products" not in content
    assert "noisy script" not in content
    assert "color: red" not in content
    assert "Home" not in content
    assert "Corporation" not in content

def test_clean_html_content_missing_h1():
    html = """
    <html>
      <head>
        <title>Fallback Title</title>
      </head>
      <body>
        <p>Some paragraph text.</p>
      </body>
    </html>
    """
    res = clean_html_content(html)
    assert res["title"] == "Fallback Title"

def test_clean_html_content_empty():
    res = clean_html_content("")
    assert res == {
        "title": "",
        "content": "",
        "source": "",
        "author": "",
        "url": "",
        "publication_date": ""
    }

def test_load_html_file():
    html = "<html><head><title>Test</title></head><body><h1>Title</h1><p>Body content</p></body></html>"
    with NamedTemporaryFile(mode="w+", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        temp_path = f.name
        
    try:
        res = load_html_file(temp_path)
        assert res["title"] == "Title"
        assert "Body content" in res["content"]
    finally:
        Path(temp_path).unlink()

def test_load_html_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_html_file("non_existent_file_12345.html")

def test_clean_html_content_missing_body():
    # Only head, no body
    html = "<html><head><title>Title Only</title></head></html>"
    res = clean_html_content(html)
    assert res["title"] == "Title Only"
    assert res["content"] == ""

def test_clean_html_content_corrupted():
    # Incomplete tags, missing closing tags
    html = "<html><head><title>Corrupted Title<body class='main'><h1>Heading text<p>Incomplete paragraph"
    res = clean_html_content(html)
    # Different parsers (lxml vs html.parser) handle unclosed tags differently.
    # We assert that either the title tag content or the h1 tag content is captured.
    assert "Corrupted Title" in res["title"] or "Heading text" in res["title"]
    assert "Heading text" in res["content"]
    assert "Incomplete paragraph" in res["content"]

def test_clean_html_content_invalid_type():
    res = clean_html_content(None)
    assert res["title"] == ""
    assert res["content"] == ""
    
    res = clean_html_content(12345)
    assert res["title"] == ""
    assert res["content"] == ""
