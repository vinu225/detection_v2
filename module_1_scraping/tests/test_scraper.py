"""
module_1/tests/test_scraper.py — Unit tests for module_1 scraper functionality.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from module_1_scraping.scraper import scrape_article
from shared.models import RawArticle


class TestScraper:
    @patch("module_1_scraping.scraper.requests.get")
    def test_scrape_article_requests_success(self, mock_get):
        # Setup mock HTML and response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com/news-item"
        mock_resp.text = (
            "<html><body>"
            "<h1>Major Breakthrough in Science</h1>"
            "<article><p>This is a highly substantive article body that contains more than enough "
            "characters to easily pass the minimum content length constraints (200 characters) "
            "of the scraper waterfall mechanism without hitting any fallbacks. The extra sentence here "
            "adds length to make sure the requests-based strategy succeeded immediately.</p></article>"
            "</body></html>"
        )
        mock_get.return_value = mock_resp

        article = scrape_article("https://example.com/news-item", use_playwright=False)
        
        assert isinstance(article, RawArticle)
        assert article.title == "Major Breakthrough in Science"
        assert "substantive article body" in article.content
        assert article.url == "https://example.com/news-item"
        assert article.source == "example.com"

    def test_scrape_invalid_url_raises(self):
        with pytest.raises(ValueError):
            scrape_article("not-a-valid-url-format")
