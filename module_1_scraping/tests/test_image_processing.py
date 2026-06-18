"""
module_1/tests/test_image_processing.py — Unit tests for image validation,
OCR extraction, and the FastAPI /collect/image endpoint.
"""

from __future__ import annotations

import io
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient

from app import app, verify_api_key
from module_1_scraping.config import get_settings
from module_1_scraping.image_processing import validate_image, extract_text_from_image, get_mime_type

settings = get_settings()


def get_valid_image_bytes(fmt: str = "PNG") -> bytes:
    """Helper to generate tiny valid image bytes in memory."""
    img = Image.new("RGB", (5, 5), color="blue")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Image Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestImageValidation:
    def test_validate_valid_image(self):
        png_bytes = get_valid_image_bytes("PNG")
        assert validate_image(png_bytes) == "PNG"

        jpeg_bytes = get_valid_image_bytes("JPEG")
        assert validate_image(jpeg_bytes) == "JPEG"

    def test_validate_invalid_image_raises(self):
        with pytest.raises(ValueError, match="Invalid or corrupted image"):
            validate_image(b"not-an-image-file-content")

    def test_validate_empty_image_raises(self):
        with pytest.raises(ValueError, match="Empty image data"):
            validate_image(b"")


class TestMimeTypeMapping:
    def test_mime_type_mappings(self):
        assert get_mime_type("PNG") == "image/png"
        assert get_mime_type("JPEG") == "image/jpeg"
        assert get_mime_type("WEBP") == "image/webp"
        assert get_mime_type("GIF") == "image/gif"


# ─────────────────────────────────────────────────────────────────────────────
# Text Extraction / OCR Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTextExtraction:
    def test_extract_text_mock_fallback(self):
        # Ensure gemini_api_key is unset for mock testing
        with patch.object(settings, "gemini_api_key", ""):
            png_bytes = get_valid_image_bytes("PNG")
            extracted = extract_text_from_image(png_bytes, "test_article_doc.png")
            assert "mocked news article" in extracted
            assert "test_article_doc.png" in extracted

    @patch("requests.post")
    def test_extract_text_via_gemini_success(self, mock_post):
        # Configure a mock API key
        with patch.object(settings, "gemini_api_key", "mock_key"):
            with patch.object(settings, "gemini_model", "gemini-2.5-flash"):
                # Stub API response structure
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Breaking News: Project successfully integrated image scraping pipeline."}
                                ]
                            }
                        }
                    ]
                }
                mock_post.return_value = mock_response

                png_bytes = get_valid_image_bytes("PNG")
                extracted = extract_text_from_image(png_bytes, "test_gemini.png")
                
                assert "Breaking News" in extracted
                mock_post.assert_called_once()
                # Verify key is passed in URL
                call_args = mock_post.call_args
                assert "key=mock_key" in call_args[0][0]


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Consolidated Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConsolidatedEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @patch("app.analyze_image_news_context")
    @patch("app.store_article")
    def test_image_processing_endpoint(self, mock_store, mock_analyze, client):
        mock_analyze.return_value = {
            "extracted_text": "Extracted image text context.",
            "news_analysis": "Contextual news analysis regarding Elon Musk net worth."
        }
        mock_store.return_value = ({}, True)

        png_bytes = get_valid_image_bytes("PNG")
        files = {"file": ("elon_musk_1trillion.png", png_bytes, "image/png")}
        
        resp = client.post("/image-processing", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["filename"] == "elon_musk_1trillion.png"
        assert "Elon Musk" in data["news_analysis"]
        assert "Extracted image text" in data["extracted_text"]
        mock_analyze.assert_called_once()
        mock_store.assert_called_once()

    @patch("app.collect_articles")
    @patch("app.store_article")
    def test_news_api_endpoint(self, mock_store, mock_collect, client):
        # Setup mock collected articles
        mock_art = MagicMock()
        mock_art.title = "AI Boom"
        mock_art.url = "https://example.com/ai"
        mock_art.content = "Artificial intelligence makes massive leaps in 2026."
        mock_art.description = "AI leaps"
        mock_art.author = "Tech Reporter"
        mock_art.source = "Tech News"
        mock_art.published_at = "2026-06-17T00:00:00Z"
        
        mock_collect.return_value = [mock_art]
        mock_store.return_value = ({}, True)

        resp = client.post("/news-api", json={"topic": "Artificial Intelligence"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["topic"] == "Artificial Intelligence"
        assert data["collected_count"] == 4  # called 4 times for gnews, newsapi, rss, search
        assert len(data["articles"]) > 0
        assert data["articles"][0]["title"] == "AI Boom"

    @patch("app.collect_articles")
    @patch("app.query_gemini_text")
    def test_llm_knowledge_endpoint(self, mock_query, mock_collect, client):
        # Setup mock search results
        mock_art = MagicMock()
        mock_art.title = "Donald Trump Update"
        mock_art.url = "https://example.com/trump"
        mock_art.content = "Latest information on Donald Trump presidency."
        mock_art.description = "Trump presidency updates."
        mock_art.author = "Political Press"
        mock_art.source = "Politics Daily"
        mock_art.published_at = "2026-06-17T00:00:00Z"

        mock_collect.return_value = [mock_art]
        mock_query.return_value = "According to search results, Donald Trump has been making major announcements."

        resp = client.post("/llm-knowledge", json={"query": "what is the recent news about Donald Trump"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Donald Trump" in data["answer"]
        assert "Politics Daily" in data["context_sources"]
