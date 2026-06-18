"""
shared/models.py — Pydantic v2 schemas used across the entire pipeline.
These are pure data-transfer / validation objects; ORM models live in shared/database.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


# ─────────────────────────────────────────────────────────────────────────────
# Raw / inbound
# ─────────────────────────────────────────────────────────────────────────────

class RawArticle(BaseModel):
    """Minimal article as returned by a news API or RSS parser."""
    title: str
    author: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    url: str
    content: Optional[str] = None          # may be truncated / raw HTML
    description: Optional[str] = None      # API-level summary


class CleanArticle(BaseModel):
    """
    Fully processed article ready for the ML pipeline.
    Matches the articles collection schema in MongoDB.
    """
    article_id: str
    title: str
    author: Optional[str] = None
    source: Optional[str] = None
    publication_date: Optional[str] = None
    url: str
    clean_text: str
    word_count: int = 0
    paragraphs: List[str] = Field(default_factory=list)
    content_hash: str
    url_hash: str
    scraped_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────────────
# API request / response bodies
# ─────────────────────────────────────────────────────────────────────────────

class CollectAPIRequest(BaseModel):
    """POST /collect/api"""
    query: Optional[str] = Field(None, description="Search keyword(s)")
    category: Optional[str] = Field(None, description="e.g. technology, sports")
    source: Optional[str] = Field(None, description="e.g. bbc-news")
    from_date: Optional[str] = Field(None, description="ISO 8601 date, e.g. 2024-01-01")
    to_date: Optional[str] = Field(None, description="ISO 8601 date, e.g. 2024-12-31")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    provider: str = Field(default="newsapi", description="newsapi | gnews | rss")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"newsapi", "gnews", "rss"}
        if v not in allowed:
            raise ValueError(f"provider must be one of {allowed}")
        return v


class CollectURLRequest(BaseModel):
    """POST /collect/url"""
    url: str
    use_playwright: bool = Field(default=False, description="Use JS rendering for SPAs")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}(?:\.\d{1,3}){3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not pattern.match(v):
            raise ValueError(f"Invalid URL: {v}")
        return v


class CleanRequest(BaseModel):
    """POST /clean — clean arbitrary raw HTML."""
    html: str
    url: Optional[str] = None


class StoreRequest(BaseModel):
    """POST /store — persist a CleanArticle."""
    article: CleanArticle


# ─────────────────────────────────────────────────────────────────────────────
# Response envelopes
# ─────────────────────────────────────────────────────────────────────────────

class ArticleResponse(BaseModel):
    success: bool = True
    article: Optional[CleanArticle] = None
    message: Optional[str] = None


class CollectResponse(BaseModel):
    success: bool = True
    collected: int = 0
    stored: int = 0
    duplicates: int = 0
    articles: List[CleanArticle] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class CleanResponse(BaseModel):
    success: bool = True
    clean_text: str = ""
    word_count: int = 0
    paragraphs: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
