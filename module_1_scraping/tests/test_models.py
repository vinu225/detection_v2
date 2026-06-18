"""
module_1/tests/test_models.py — Pydantic model validation tests.
Run with: pytest module_1/tests/ -v
"""

import pytest

from shared.models import CollectAPIRequest, CollectURLRequest


class TestCollectAPIRequest:
    def test_valid_provider(self):
        req = CollectAPIRequest(provider="newsapi", query="AI")
        assert req.provider == "newsapi"

    def test_invalid_provider_raises(self):
        with pytest.raises(Exception):
            CollectAPIRequest(provider="invalid_source")

    def test_default_pagination(self):
        req = CollectAPIRequest()
        assert req.page == 1
        assert req.page_size == 20


class TestCollectURLRequest:
    def test_valid_url_accepted(self):
        req = CollectURLRequest(url="https://example.com/article")
        assert req.url == "https://example.com/article"

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            CollectURLRequest(url="not-a-url")

    def test_ftp_url_rejected(self):
        with pytest.raises(Exception):
            CollectURLRequest(url="ftp://example.com/file")
