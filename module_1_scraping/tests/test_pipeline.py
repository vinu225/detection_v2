"""
module_1/tests/test_pipeline.py — Unit tests for news collection and ingestion pipelines.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from module_1_scraping.pipeline import run_api_collection_pipeline, run_url_collection_pipeline
from shared.models import CleanArticle


class TestCollectionPipelines:
    @patch("module_1_scraping.pipeline.collect_articles")
    @patch("module_1_scraping.pipeline.store_article")
    def test_run_api_collection_pipeline_success(self, mock_store, mock_collect):
        # 1. Mock news collector to return one raw article
        mock_raw = MagicMock()
        mock_raw.title = "Example Headline"
        mock_raw.url = "https://example.com/item"
        mock_raw.content = "Substantive body text for testing the pipeline functions."
        mock_raw.description = "Summary description"
        mock_raw.author = "Author Name"
        mock_raw.source = "Source Name"
        mock_raw.published_at = "2026-06-17T00:00:00Z"
        
        mock_collect.return_value = [mock_raw]
        
        # 2. Mock store_article response
        mock_store.return_value = ({}, True)
        
        db_mock = MagicMock()
        res = run_api_collection_pipeline(db_mock, provider="newsapi", query="test")
        
        assert res["collected"] == 1
        assert res["stored"] == 1
        assert res["duplicates"] == 0
        assert len(res["errors"]) == 0
        assert len(res["articles"]) == 1
        assert isinstance(res["articles"][0], CleanArticle)

    @patch("module_1_scraping.pipeline.scrape_article")
    @patch("module_1_scraping.pipeline.store_article")
    def test_run_url_collection_pipeline_success(self, mock_store, mock_scrape):
        mock_raw = MagicMock()
        mock_raw.title = "Example URL Headline"
        mock_raw.url = "https://example.com/url-item"
        mock_raw.content = "Substantive scraped body text for testing the pipeline functions."
        mock_raw.description = "Scraped description"
        mock_raw.author = "Scraped Author"
        mock_raw.source = "Scraped Source"
        mock_raw.published_at = "2026-06-17T00:00:00Z"
        
        mock_scrape.return_value = mock_raw
        mock_store.return_value = ({}, True)
        
        db_mock = MagicMock()
        article, is_new = run_url_collection_pipeline(db_mock, "https://example.com/url-item")
        
        assert is_new is True
        assert isinstance(article, CleanArticle)
        assert article.title == "Example URL Headline"
