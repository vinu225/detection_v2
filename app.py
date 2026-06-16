"""
app.py — FastAPI application entry point.

Run with:
    uvicorn app:app --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.database import Database

from config import get_settings
from database import (
    check_db_connection,
    delete_article,
    get_article_by_id,
    get_db,
    get_all_articles,
    init_db,
    store_article,
)
from logger import get_logger
from models import (
    ArticleResponse,
    CleanArticle,
    CleanRequest,
    CleanResponse,
    CollectAPIRequest,
    CollectResponse,
    CollectURLRequest,
    ErrorResponse,
    HealthResponse,
    StoreRequest,
)
from news_collector import collect_articles
from preprocessor import build_clean_article, clean_html
from scraper import scrape_article

log = get_logger("app")
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting News Pipeline API …")
    db_ok = init_db()
    if db_ok:
        log.info("Database ready.")
    else:
        log.warning(
            "Database not reachable at startup — some endpoints will return 503."
        )
    yield
    log.info("Shutting down News Pipeline API.")


# ─────────────────────────────────────────────────────────────────────────────
# App instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="News Collection & Preprocessing API",
    description=(
        "Collect news articles from APIs and websites, clean HTML content, "
        "structure the data, and store it for downstream ML pipelines."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Middleware — request logging + timing
# ─────────────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    log.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info("← %s %s  status=%d  %.1fms", request.method, request.url.path, response.status_code, elapsed)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Exception handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(error="Validation error", detail=str(exc)).model_dump(),
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(error="Internal error", detail=str(exc)).model_dump(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
def health_check():
    db_status = "ok" if check_db_connection() else "unavailable"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        timestamp=datetime.utcnow().isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /collect/api
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/collect/api",
    response_model=CollectResponse,
    summary="Collect articles from a news API",
    tags=["Collection"],
)
def collect_from_api(
    req: CollectAPIRequest,
    db: Database = Depends(get_db),
):
    """
    Collect articles from **NewsAPI**, **GNews**, or **RSS** feeds.
    Articles are automatically cleaned and stored; duplicates are skipped.
    """
    log.info("POST /collect/api  provider=%s query=%r", req.provider, req.query)

    raw_articles = collect_articles(
        provider=req.provider,
        query=req.query,
        category=req.category,
        source=req.source,
        from_date=req.from_date,
        to_date=req.to_date,
        page=req.page,
        page_size=req.page_size,
    )

    result = CollectResponse(collected=len(raw_articles))
    errors: List[str] = []

    for raw in raw_articles:
        try:
            clean = build_clean_article(raw)
            _, is_new = store_article(db, clean)
            if is_new:
                result.stored += 1
                result.articles.append(clean)
            else:
                result.duplicates += 1
        except Exception as exc:
            msg = f"Error processing {raw.url}: {exc}"
            log.error(msg)
            errors.append(msg)

    result.errors = errors
    log.info(
        "collect/api done: collected=%d stored=%d dups=%d errors=%d",
        result.collected, result.stored, result.duplicates, len(errors),
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# POST /collect/url
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/collect/url",
    response_model=ArticleResponse,
    summary="Scrape and store a single article URL",
    tags=["Collection"],
)
def collect_from_url(
    req: CollectURLRequest,
    db: Database = Depends(get_db),
):
    """
    Scrape a full article from a direct URL, clean it, and store it.
    Set `use_playwright=true` for JavaScript-rendered pages.
    """
    log.info("POST /collect/url  url=%s  playwright=%s", req.url, req.use_playwright)

    try:
        raw = scrape_article(req.url, use_playwright=req.use_playwright)
    except (ValueError, RuntimeError) as exc:
        log.error("Scraping failed for %s: %s", req.url, exc)
        raise HTTPException(status_code=422, detail=str(exc))

    clean = build_clean_article(raw)
    _, is_new = store_article(db, clean)

    msg = "Article stored." if is_new else "Duplicate — article already in database."
    log.info("collect/url: %s  article_id=%s", msg, clean.article_id)
    return ArticleResponse(article=clean, message=msg)


# ─────────────────────────────────────────────────────────────────────────────
# POST /clean
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/clean",
    response_model=CleanResponse,
    summary="Clean raw HTML and return structured text",
    tags=["Processing"],
)
def clean_html_endpoint(req: CleanRequest):
    """
    Accept raw HTML (or plain text), strip noise, normalize, and return
    clean text + paragraph list.  Nothing is stored.
    """
    log.info("POST /clean  html_len=%d", len(req.html))
    clean_text, paragraphs = clean_html(req.html, base_url=req.url)
    return CleanResponse(
        clean_text=clean_text,
        word_count=len(clean_text.split()),
        paragraphs=paragraphs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /store
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/store",
    response_model=ArticleResponse,
    summary="Persist a pre-processed CleanArticle",
    tags=["Storage"],
)
def store_endpoint(
    req: StoreRequest,
    db: Database = Depends(get_db),
):
    """
    Store an already-processed CleanArticle object directly.
    Useful when pre-processing happens outside this service.
    """
    log.info("POST /store  article_id=%s", req.article.article_id)
    _, is_new = store_article(db, req.article)
    msg = "Article stored." if is_new else "Duplicate — article already in database."
    return ArticleResponse(article=req.article, message=msg)


# ─────────────────────────────────────────────────────────────────────────────
# GET /article/{id}
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/article/{article_id}",
    response_model=ArticleResponse,
    summary="Retrieve a stored article by ID",
    tags=["Storage"],
)
def get_article(article_id: str, db: Database = Depends(get_db)):
    """Fetch a stored article by its UUID."""
    log.info("GET /article/%s", article_id)
    article = get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id!r} not found.")
    return ArticleResponse(article=article)


# ─────────────────────────────────────────────────────────────────────────────
# GET /articles  (bonus listing endpoint for ML pipelines)
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/articles",
    response_model=List[CleanArticle],
    summary="List stored articles (paginated)",
    tags=["Storage"],
)
def list_articles(
    skip: int = 0,
    limit: int = 50,
    db: Database = Depends(get_db),
):
    """Return a paginated list of all stored articles."""
    return get_all_articles(db, skip=skip, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /article/{id}
# ─────────────────────────────────────────────────────────────────────────────

@app.delete(
    "/article/{article_id}",
    summary="Delete an article by ID",
    tags=["Storage"],
)
def delete_article_endpoint(article_id: str, db: Database = Depends(get_db)):
    log.info("DELETE /article/%s", article_id)
    deleted = delete_article(db, article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Article {article_id!r} not found.")
    return {"success": True, "message": f"Article {article_id} deleted."}
