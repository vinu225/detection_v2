"""
module_1/tests/test_preprocessor.py — Unit tests for module_1 preprocessing.
Run with: pytest module_1/tests/ -v
"""

import hashlib
import pytest

from module_1_scraping.preprocessing import clean_html, build_clean_article
from module_1_scraping.content_extractor import extract_paragraphs
from shared.utils import normalize_text, sha256
from shared.models import RawArticle


# ─────────────────────────────────────────────────────────────────────────────
# normalize_text tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_smart_quotes_replaced(self):
        text = "\u201cHello\u201d and \u2018world\u2019"
        result = normalize_text(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_excess_whitespace_collapsed(self):
        result = normalize_text("hello   world\n\n\n\nfoo")
        assert "  " not in result

    def test_unicode_normalized(self):
        # \ufb01 is the 'fi' ligature; NFKC maps it to 'fi'
        result = normalize_text("\ufb01le")
        assert result == "file"


# ─────────────────────────────────────────────────────────────────────────────
# extract_paragraphs tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractParagraphs:
    def test_short_paragraphs_dropped(self):
        text = "Hi.\n\nThis is a short sentence.\n\nThis paragraph is long enough to survive the minimum word count filter and should be kept intact."
        paras = extract_paragraphs(text)
        assert len(paras) == 1
        assert "long enough" in paras[0]

    def test_duplicate_paragraphs_dropped(self):
        para = "The quick brown fox jumps over the lazy dog and keeps going for a while."
        text = f"{para}\n\n{para}\n\n{para}"
        paras = extract_paragraphs(text)
        assert len(paras) == 1

    def test_multiple_unique_paragraphs_kept(self):
        text = (
            "Scientists discovered a new species of deep-sea fish in the Pacific Ocean last week.\n\n"
            "The economy grew by three percent in the second quarter according to government data.\n\n"
            "Local authorities announced a new public transport initiative for the city centre."
        )
        paras = extract_paragraphs(text)
        assert len(paras) == 3


# ─────────────────────────────────────────────────────────────────────────────
# clean_html tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanHtml:
    def test_strips_scripts_and_styles(self):
        html = "<html><head><style>body{color:red}</style></head><body><script>alert(1)</script><p>Real content here that is long enough to survive filtering.</p></body></html>"
        text, _ = clean_html(html)
        assert "alert" not in text
        assert "color:red" not in text

    def test_returns_clean_text(self):
        html = "<article><p>Breaking news: Scientists confirm that climate change is accelerating faster than previously predicted by global models.</p></article>"
        text, paras = clean_html(html)
        assert "Breaking news" in text
        assert len(paras) >= 1

    def test_empty_html_returns_empty(self):
        text, paras = clean_html("")
        assert text == ""
        assert paras == []

    def test_strips_nav_and_footer(self):
        html = """
        <html><body>
          <nav>Home | About | Contact</nav>
          <article>
            <p>The main article content is here and it is long enough to be kept by the paragraph filter.</p>
          </article>
          <footer>Copyright 2024 Example Corp</footer>
        </body></html>
        """
        text, _ = clean_html(html)
        assert "Home | About" not in text
        assert "Copyright" not in text
        assert "main article content" in text


# ─────────────────────────────────────────────────────────────────────────────
# build_clean_article tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCleanArticle:
    def test_article_id_is_deterministic(self):
        raw = RawArticle(
            title="Test",
            url="https://example.com/article-1",
            content="Some content for this article.",
        )
        a1 = build_clean_article(raw)
        a2 = build_clean_article(raw)
        assert a1.article_id == a2.article_id

    def test_hashes_generated(self):
        raw = RawArticle(
            title="Test Article",
            url="https://example.com/test",
            content="<p>Content that is definitely real and substantive enough for hashing purposes.</p>",
        )
        article = build_clean_article(raw)
        assert len(article.content_hash) == 64   # SHA-256 hex
        assert len(article.url_hash) == 64

    def test_word_count_computed(self):
        raw = RawArticle(
            title="Test",
            url="https://example.com/wc",
            content="<p>" + " ".join(["word"] * 50) + "</p>",
        )
        article = build_clean_article(raw)
        assert article.word_count > 0

    def test_fallback_to_description(self):
        raw = RawArticle(
            title="Test",
            url="https://example.com/desc",
            content=None,
            description="This is a meaningful description that contains enough words to pass through.",
        )
        article = build_clean_article(raw)
        assert "meaningful description" in article.clean_text


# ─────────────────────────────────────────────────────────────────────────────
# sha256 utility tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSha256:
    def test_matches_hashlib(self):
        text = "hello world"
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert sha256(text) == expected

    def test_different_inputs_differ(self):
        assert sha256("abc") != sha256("xyz")
