"""
database.py — MongoDB client layer for managing article storage.
Handles database connections, index verification, CRUD operations,
and duplicate detection via content / URL hashes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Generator

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError

from config import get_settings
from logger import get_logger
from models import CleanArticle

log = get_logger("database")
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Client Initialization (Singleton)
# ─────────────────────────────────────────────────────────────────────────────

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Singleton MongoDB client — reuses connection pool across requests."""
    global _client
    if _client is None:
        _client = MongoClient(
            settings.database_url,
            maxPoolSize=15,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )
        log.info("MongoDB client created for URI: %s", settings.database_url)
    return _client


def _get_db_name() -> str:
    """Extract the DB name from the connection URI; fall back to 'news_detection'."""
    try:
        return get_client().get_default_database().name
    except Exception:
        return "news_detection"


def get_db() -> Generator[Database, None, None]:
    """
    FastAPI dependency — yields a MongoDB Database instance.
    Safely extracts the DB name from the URI; falls back to 'news_detection'.
    """
    db = get_client()[_get_db_name()]
    try:
        yield db
    finally:
        # MongoClient manages its own connection pool; nothing to close here.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Schema & Index Management
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> bool:
    """
    Ensures required unique indexes exist on the articles collection.
    Safe to call on every startup — MongoDB skips creation if they exist.

    FIX 3: Removed background=True which is deprecated in PyMongo >= 4.0
            and raises a TypeError.
    """
    try:
        db_name = _get_db_name()
        articles_col = get_client()[db_name]["articles"]

        # Unique indexes replace PostgreSQL's UniqueConstraint
        articles_col.create_index("url_hash", unique=True)
        articles_col.create_index("content_hash", unique=True)
        # Useful for fast lookups by URL
        articles_col.create_index("url", sparse=True)

        log.info("MongoDB indexes verified on db='%s' collection='articles'.", db_name)
        return True
    except PyMongoError as exc:
        log.error("Failed to initialize MongoDB indexes: %s", exc)
        return False


def check_db_connection() -> bool:
    """Ping MongoDB — used by GET /health."""
    try:
        get_client().admin.command("ping")
        return True
    except ConnectionFailure as exc:
        log.error("MongoDB health-check failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CRUD Operations
# ─────────────────────────────────────────────────────────────────────────────

def store_article(db: Database, article: CleanArticle) -> tuple[dict | None, bool]:
    """
    Persist a CleanArticle to MongoDB.
    Returns (document, is_new). is_new=False means a duplicate was detected.
    """
    articles_col = db["articles"]

    # Pre-check for duplicates before attempting insert
    existing = articles_col.find_one({
        "$or": [
            {"url_hash": article.url_hash},
            {"content_hash": article.content_hash},
        ]
    })
    if existing:
        log.info(
            "Duplicate detected — article_id=%s url=%s",
            article.article_id, article.url,
        )
        return existing, False

    # MongoDB stores lists natively — no json.dumps() needed (unlike PostgreSQL)
    article_doc = {
        "_id": article.article_id or str(uuid.uuid4()),
        "title": article.title,
        "author": article.author,
        "source": article.source,
        "publication_date": article.publication_date,
        "url": article.url,
        "content": article.clean_text,
        "content_hash": article.content_hash,
        "url_hash": article.url_hash,
        "word_count": article.word_count,
        "paragraphs": article.paragraphs or [],   # stored as native BSON array
        "created_at": datetime.now(timezone.utc),
    }

    try:
        articles_col.insert_one(article_doc)
        log.info(
            "Stored new article id=%s title=%r",
            article_doc["_id"], article_doc["title"][:60],
        )
        return article_doc, True
    except DuplicateKeyError:
        # Race condition — another worker inserted the same article concurrently
        log.warning(
            "DuplicateKeyError on article_id=%s (concurrent insert?)",
            article.article_id,
        )
        existing = articles_col.find_one({
            "$or": [
                {"url_hash": article.url_hash},
                {"content_hash": article.content_hash},
            ]
        })
        return existing, False
    except PyMongoError as exc:
        log.error("DB write error on article_id=%s: %s", article.article_id, exc)
        return None, False


def get_article_by_id(db: Database, article_id: str) -> CleanArticle | None:
    """Retrieve a single article by its _id."""
    doc = db["articles"].find_one({"_id": article_id})
    return _doc_to_clean(doc) if doc else None


def get_all_articles(db: Database, skip: int = 0, limit: int = 50) -> List[CleanArticle]:
    """Paginated article listing for ML pipeline consumption."""
    cursor = db["articles"].find().skip(skip).limit(limit)
    return [_doc_to_clean(doc) for doc in cursor]


def delete_article(db: Database, article_id: str) -> bool:
    """Delete an article by its _id. Returns True if deleted, False if not found."""
    result = db["articles"].delete_one({"_id": article_id})
    if result.deleted_count == 0:
        return False
    log.info("Deleted article id=%s", article_id)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helper
# ─────────────────────────────────────────────────────────────────────────────

def _doc_to_clean(doc: dict) -> CleanArticle:
    """Translate a raw MongoDB BSON document into a CleanArticle Pydantic model."""
    created_at = doc.get("created_at")
    return CleanArticle(
        article_id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        author=doc.get("author"),
        source=doc.get("source"),
        publication_date=doc.get("publication_date"),
        url=doc.get("url", ""),
        clean_text=doc.get("content", ""),
        word_count=doc.get("word_count", 0),
        paragraphs=doc.get("paragraphs", []),
        content_hash=doc.get("content_hash", ""),
        url_hash=doc.get("url_hash", ""),
        scraped_at=created_at.isoformat() if isinstance(created_at, datetime) else "",
    )