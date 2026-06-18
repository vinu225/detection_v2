"""
app.py — FastAPI application entry point.
Consolidated modular news pipeline:
  1. POST /image-processing : Multimodal OCR and context analysis via Gemini
  2. POST /news-api         : Topic-based news query and MongoDB storage
  3. POST /llm-knowledge    : Retrieval-Augmented Generation (web scraping + LLM synthesis)
  4. GET /                  : Premium playground UI dashboard
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from pymongo.database import Database

from module_1_scraping.config import get_settings
from module_1_scraping.image_processing import (
    analyze_image_news_context,
    extract_text_from_image,
    query_gemini_text,
)
from module_1_scraping.news_collector import collect_articles
from module_1_scraping.preprocessing import build_clean_article
from shared.database import (
    check_db_connection,
    get_db,
    init_db,
    store_article,
)
from shared.logger import get_logger
from shared.models import ArticleResponse, CleanArticle, ErrorResponse, HealthResponse, RawArticle
from pipeline_orchestrator import run_unified_pipeline, OUTPUT_DIR

log = get_logger("app")
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting News Reorganized API Pipeline …")
    db_ok = init_db()
    if db_ok:
        log.info("Database ready.")
    else:
        log.warning("Database not reachable at startup.")
    yield
    log.info("Shutting down News Reorganized API Pipeline.")


app = FastAPI(
    title="Reorganized News Pipeline API",
    description="Refactored pipeline with consolidated multimodal endpoints and LLM RAG capability.",
    version="2.0.0",
    lifespan=lifespan,
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
    log.info(">> %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info("<< %s %s  status=%d  %.1fms", request.method, request.url.path, response.status_code, elapsed)
    return response

# ─────────────────────────────────────────────────────────────────────────────
# API Key Verification (Optional / Enforced if configured)
# ─────────────────────────────────────────────────────────────────────────────

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Depends(api_key_header)):
    expected_key = settings.pipeline_api_key
    if not expected_key:
        return
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials — Invalid API Key",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas for Requests
# ─────────────────────────────────────────────────────────────────────────────

class NewsRequest(BaseModel):
    topic: str = Field(..., description="The query topic to search news for")


class LLMRequest(BaseModel):
    query: str = Field(..., description="Your question to the LLM (e.g., 'what is the recent news about Donald Trump')")


class UnifiedPipelineRequest(BaseModel):
    topic: str = Field(..., description="The search topic for the unified pipeline")
    include_news_api: bool = Field(default=True, description="Collect articles from news providers")
    include_llm_knowledge: bool = Field(default=True, description="Enable LLM web synthesis")
    output_format: str = Field(default="json", description="Output format: 'json' or 'html'")
    strategy: str = Field(default="mean", description="Sentiment aggregation strategy: 'mean' or 'weighted'")


# ─────────────────────────────────────────────────────────────────────────────
# 1) POST /image-processing
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/image-processing",
    summary="OCR & Context News Analysis from Image",
    tags=["Pipeline"],
)
async def image_processing_endpoint(
    file: UploadFile = File(...),
    db: Database = Depends(get_db),
):
    """
    Accepts an uploaded image, performs OCR text extraction, generates a professional
    contextual analysis using the configured Gemini model, and stores the result in MongoDB.
    """
    log.info("POST /image-processing  filename=%s", file.filename)
    
    try:
        content_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to read upload: {exc}")

    # Validate and process
    try:
        results = analyze_image_news_context(content_bytes, filename=file.filename or "image.png")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Store in MongoDB for downstream tasks
    raw_article = RawArticle(
        title=f"Image Analysis - {file.filename or 'Unnamed'}",
        author="Gemini OCR Processor",
        source="Uploaded Image",
        published_at=datetime.now(timezone.utc).isoformat(),
        url=f"https://image-pipeline.local/{uuid.uuid4()}",
        content=results["extracted_text"],
        description=results["news_analysis"]
    )
    
    try:
        clean = build_clean_article(raw_article)
        store_article(db, clean)
    except Exception as exc:
        log.warning("Could not store image analysis to DB: %s", exc)

    return {
        "success": True,
        "filename": file.filename,
        "extracted_text": results["extracted_text"],
        "news_analysis": results["news_analysis"]
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2) POST /news-api
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/news-api",
    summary="Query, Clean, and Store News by Topic",
    tags=["Pipeline"],
)
async def news_api_endpoint(
    req: NewsRequest,
    db: Database = Depends(get_db),
):
    """
    Queries news providers (NewsAPI, GNews, RSS feeds, and DuckDuckGo Web Search) for a topic,
    normalizes and preprocesses the gathered articles, and stores them in MongoDB.
    """
    log.info("POST /news-api  topic=%r", req.topic)
    
    # Ingest from all providers
    providers = ["gnews", "newsapi", "rss", "search"]
    all_raw_articles = []
    
    for p in providers:
        try:
            log.info("Querying news provider: %s", p)
            articles = collect_articles(provider=p, query=req.topic, page_size=10)
            all_raw_articles.extend(articles)
        except Exception as exc:
            log.warning("Ingestion provider %s failed: %s", p, exc)

    if not all_raw_articles:
        log.warning("No articles collected for topic: %s", req.topic)
        return {
            "success": True,
            "topic": req.topic,
            "collected_count": 0,
            "stored_count": 0,
            "articles": []
        }

    stored_articles = []
    duplicates = 0
    errors = 0

    for raw in all_raw_articles:
        try:
            clean = build_clean_article(raw)
            _, is_new = store_article(db, clean)
            if is_new:
                stored_articles.append({
                    "title": clean.title,
                    "source": clean.source,
                    "url": clean.url,
                    "clean_text": clean.clean_text[:300] + "..." if len(clean.clean_text) > 300 else clean.clean_text
                })
            else:
                duplicates += 1
        except Exception as exc:
            log.error("Pipeline indexing failed: %s", exc)
            errors += 1

    return {
        "success": True,
        "topic": req.topic,
        "collected_count": len(all_raw_articles),
        "stored_count": len(stored_articles),
        "duplicates_skipped": duplicates,
        "errors": errors,
        "articles": stored_articles
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3) POST /llm-knowledge
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/llm-knowledge",
    summary="Scrape & Synthesize Knowledge via RAG",
    tags=["Pipeline"],
)
async def llm_knowledge_endpoint(
    req: LLMRequest,
):
    """
    Given a prompt, extracts query keywords, fetches/scrapes corresponding news
    from websites (using web search scraping of social platforms like Reddit, Twitter),
    feeds the scraped text context into Gemini, and synthesizes a comprehensive response.
    """
    log.info("POST /llm-knowledge  query=%r", req.query)
    
    # 1. Simple heuristic keyword extraction
    # Remove common filler words to extract the noun subjects
    clean_query = req.query.lower()
    clean_query = re.sub(r"\b(what|is|are|the|recent|news|about|about|of|who|info|for|on)\b", "", clean_query)
    keywords = [kw.strip() for kw in clean_query.split() if len(kw.strip()) > 2]
    topic = " ".join(keywords) if keywords else req.query
    
    log.info("Extracted search query topic: %r", topic)

    # 2. Retrieve recent web news as context using our search scraper
    context_builder = []
    retrieved_sources = []
    
    # We query: General web, Reddit, and Twitter context via search engine scraping
    queries_to_search = [
        topic,
        f"{topic} reddit",
        f"{topic} twitter"
    ]
    
    for q in queries_to_search:
        try:
            log.info("Scraping search context for query: %r", q)
            articles = collect_articles(provider="search", query=q, page_size=4)
            for art in articles:
                content = art.content or art.description or ""
                if len(content) > 10:
                    context_builder.append(
                        f"Source: {art.source or 'Web news'}\n"
                        f"Title: {art.title}\n"
                        f"Content: {content[:800]}\n"
                    )
                    retrieved_sources.append(art.source or "Web Link")
        except Exception as exc:
            log.warning("Web context collection failed for %r: %s", q, exc)

    # Fallback to RSS/GNews if search scraping returned nothing
    if not context_builder:
        try:
            log.info("Web scraping search returned no results, falling back to RSS feeds...")
            articles = collect_articles(provider="rss", query=topic, page_size=8)
            for art in articles:
                content = art.content or art.description or ""
                if len(content) > 10:
                    context_builder.append(
                        f"Source: {art.source or 'RSS Feed'}\n"
                        f"Title: {art.title}\n"
                        f"Content: {content[:800]}\n"
                    )
                    retrieved_sources.append(art.source or "RSS Feed")
        except Exception as exc:
            log.warning("RSS fallback failed: %s", exc)

    context_str = "\n---\n".join(context_builder) if context_builder else "No external web articles found."
    
    # 3. Formulate prompt for Gemini
    system_prompt = (
        "You are an advanced news synthesis agent. Your task is to answer the user's question "
        "comprehensively. Use both your own knowledge and the provided live web scraped search context "
        "to construct a detailed, factual, and informative response.\n\n"
        f"User Question: {req.query}\n\n"
        "Retrieved Web Context (including news, blogs, and social platforms like Reddit/Twitter):\n"
        f"{context_str}\n\n"
        "Please provide a well-structured answer, citing sources if relevant. Avoid making up facts."
    )

    # 4. Generate answer via Gemini
    try:
        answer = query_gemini_text(system_prompt)
    except Exception as exc:
        log.error("Gemini text synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM synthesis failure: {exc}")

    return {
        "success": True,
        "query": req.query,
        "context_sources": list(set(retrieved_sources)),
        "answer": answer
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4) POST /unified-pipeline
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/unified-pipeline",
    summary="Unified Pipeline — Collect, Analyze & Report",
    tags=["Pipeline"],
)
async def unified_pipeline_endpoint(
    topic: str = Form(...),
    include_news_api: bool = Form(True),
    include_llm_knowledge: bool = Form(True),
    include_image: bool = Form(False),
    output_format: str = Form("json"),
    strategy: str = Form("mean"),
    file: Optional[UploadFile] = File(None),
    db: Database = Depends(get_db),
):
    """
    Unified pipeline that orchestrates all three data sources
    (image-processing, news-api, llm-knowledge), runs RoBERTa sentiment
    analysis on every collected article, and generates a downloadable
    JSON or HTML report file.
    """
    log.info(
        "POST /unified-pipeline  topic=%r news_api=%s llm=%s image=%s format=%s",
        topic, include_news_api, include_llm_knowledge, include_image, output_format,
    )

    # Validate output format
    if output_format not in ("json", "html"):
        raise HTTPException(status_code=422, detail="output_format must be 'json' or 'html'")

    # Read image bytes if provided
    image_bytes = None
    image_filename = "image.png"
    if include_image and file is not None:
        try:
            image_bytes = await file.read()
            image_filename = file.filename or "image.png"
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Failed to read uploaded image: {exc}")

    # Run the orchestrator
    try:
        result = run_unified_pipeline(
            topic=topic,
            db=db,
            image_bytes=image_bytes,
            image_filename=image_filename,
            include_news_api=include_news_api,
            include_llm_knowledge=include_llm_knowledge,
            include_image=include_image,
            output_format=output_format,
            strategy=strategy,
        )
    except Exception as exc:
        log.error("Unified pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}")

    return result.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# GET /output/{filename} — Serve generated report files
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/output/{filename}",
    summary="Download generated report file",
    tags=["Pipeline"],
)
async def serve_output_file(filename: str):
    """Serve a generated JSON or HTML report file from the output directory."""
    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    filepath = OUTPUT_DIR / safe_name

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Report file not found: {safe_name}")

    media_type = "text/html" if safe_name.endswith(".html") else "application/json"
    return FileResponse(
        path=str(filepath),
        filename=safe_name,
        media_type=media_type,
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
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET / (Premium Playground UI Dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def dashboard_home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Intelligence News Pipeline Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Plus Jakarta Sans', sans-serif;
                background-color: #080C14;
                color: #E2E8F0;
            }
            .glass {
                background: rgba(15, 23, 42, 0.45);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            .glow-btn {
                background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #06B6D4 100%);
                transition: all 0.3s ease;
            }
            .glow-btn:hover {
                box-shadow: 0 0 20px rgba(124, 58, 237, 0.5);
                transform: translateY(-1px);
            }
            .card-glow:hover {
                box-shadow: 0 0 30px rgba(79, 70, 229, 0.15);
                border-color: rgba(79, 70, 229, 0.3);
            }
            /* Custom Scrollbar */
            ::-webkit-scrollbar {
                width: 6px;
            }
            ::-webkit-scrollbar-track {
                background: #080C14;
            }
            ::-webkit-scrollbar-thumb {
                background: #1E293B;
                border-radius: 4px;
            }
        </style>
    </head>
    <body class="min-h-screen relative overflow-x-hidden pb-12">
        <!-- Background Orbs -->
        <div class="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none"></div>
        <div class="absolute bottom-[20%] right-[-10%] w-[600px] h-[600px] bg-cyan-900/10 rounded-full blur-[140px] pointer-events-none"></div>

        <header class="max-w-7xl mx-auto px-6 pt-8 pb-4 flex justify-between items-center border-b border-white/5">
            <div>
                <h1 class="text-2xl font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-transparent">
                    AetherNews Pipeline
                </h1>
                <p class="text-xs text-slate-500 mt-1 font-mono">INTELLIGENT MULTIMODAL INGESTION ENGINE</p>
            </div>
            <div class="flex items-center gap-4">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span class="w-1.5 h-1.5 mr-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                    API Active
                </span>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-6 mt-12 grid grid-cols-1 lg:grid-cols-12 gap-8">
            <!-- Navigation Sidebar Tabs -->
            <div class="lg:col-span-3 flex flex-col gap-3">
                <button onclick="switchTab('image-tab')" id="btn-image-tab" class="tab-btn w-full text-left px-5 py-4 rounded-xl font-medium text-sm glass border-indigo-500/30 text-indigo-400 transition-all flex items-center gap-3 card-glow">
                    <span>🖼️</span> Multimodal OCR
                </button>
                <button onclick="switchTab('news-tab')" id="btn-news-tab" class="tab-btn w-full text-left px-5 py-4 rounded-xl font-medium text-sm glass text-slate-400 border-white/5 transition-all flex items-center gap-3 card-glow">
                    <span>📰</span> Topic News Ingestion
                </button>
                <button onclick="switchTab('llm-tab')" id="btn-llm-tab" class="tab-btn w-full text-left px-5 py-4 rounded-xl font-medium text-sm glass text-slate-400 border-white/5 transition-all flex items-center gap-3 card-glow">
                    <span>🧠</span> LLM Knowledge
                </button>
                <div class="mt-2 border-t border-white/5 pt-3">
                    <button onclick="switchTab('unified-tab')" id="btn-unified-tab" class="tab-btn w-full text-left px-5 py-4 rounded-xl font-medium text-sm glass text-slate-400 border-white/5 transition-all flex items-center gap-3 card-glow">
                        <span>🔗</span> Unified Pipeline
                    </button>
                </div>
            </div>

            <!-- Content Panel -->
            <div class="lg:col-span-9">
                <!-- Multimodal OCR Tab -->
                <div id="image-tab" class="tab-content flex flex-col gap-6">
                    <div class="glass rounded-2xl p-6 border-white/10 flex flex-col gap-4">
                        <h2 class="text-lg font-semibold text-slate-200">Multimodal OCR & Image News Analysis</h2>
                        <p class="text-sm text-slate-400">
                            Upload an image to perform OCR extraction, analyze it with the Gemini model, and retrieve recent news insights about the subject matter.
                        </p>
                        
                        <form id="image-form" onsubmit="submitImage(event)" class="mt-4 flex flex-col gap-4">
                            <div class="border-2 border-dashed border-white/10 hover:border-indigo-500/30 rounded-xl p-8 text-center cursor-pointer transition-all relative flex flex-col items-center justify-center bg-white/[0.01]">
                                <input type="file" id="image-file" name="file" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer" onchange="previewImage(event)">
                                <div id="preview-placeholder">
                                    <span class="text-4xl block mb-2">📁</span>
                                    <p class="text-sm text-indigo-400 font-medium">Click or Drag Image Here</p>
                                    <p class="text-xs text-slate-500 mt-1">PNG, JPG, WEBP formats supported</p>
                                </div>
                                <img id="image-preview-element" class="hidden max-h-48 rounded-lg border border-white/10" />
                            </div>
                            <button type="submit" class="glow-btn py-3 px-6 rounded-xl text-sm font-semibold text-white mt-2">
                                Process Image
                            </button>
                        </form>
                    </div>
                </div>

                <!-- Topic News Ingestion Tab -->
                <div id="news-tab" class="tab-content hidden flex flex-col gap-6">
                    <div class="glass rounded-2xl p-6 border-white/10 flex flex-col gap-4">
                        <h2 class="text-lg font-semibold text-slate-200">Topic News Ingestion & Sync</h2>
                        <p class="text-sm text-slate-400">
                            Queries NewsAPI, GNews, and RSS feeds in parallel for a keyword topic, pre-processes the retrieved documents, and stores unique articles in MongoDB.
                        </p>
                        
                        <form onsubmit="submitNews(event)" class="mt-4 flex flex-col gap-4">
                            <div class="flex flex-col gap-2">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Search Keyword / Topic</label>
                                <input type="text" id="news-topic" placeholder="e.g. Artificial Intelligence, Market Crash" class="w-full bg-[#0E1524] border border-white/10 focus:border-indigo-500/50 outline-none rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 transition-all">
                            </div>
                            <button type="submit" class="glow-btn py-3 px-6 rounded-xl text-sm font-semibold text-white mt-2">
                                Search & Sync Ingestion
                            </button>
                        </form>
                    </div>
                </div>

                <!-- LLM RAG Knowledge Tab -->
                <div id="llm-tab" class="tab-content hidden flex flex-col gap-6">
                    <div class="glass rounded-2xl p-6 border-white/10 flex flex-col gap-4">
                        <h2 class="text-lg font-semibold text-slate-200">LLM RAG Knowledge Agent</h2>
                        <p class="text-sm text-slate-400">
                            Asks the Gemini model a question, automatically scrapes the live web for context, and generates a structured synthesis answering the prompt.
                        </p>
                        
                        <form onsubmit="submitLLM(event)" class="mt-4 flex flex-col gap-4">
                            <div class="flex flex-col gap-2">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Your Question / Prompt</label>
                                <textarea id="llm-query" rows="3" placeholder="e.g. what is the recent news about Donald Trump?" class="w-full bg-[#0E1524] border border-white/10 focus:border-indigo-500/50 outline-none rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 transition-all resize-none"></textarea>
                            </div>
                            <button type="submit" class="glow-btn py-3 px-6 rounded-xl text-sm font-semibold text-white mt-2">
                                Synthesize Knowledge
                            </button>
                        </form>
                    </div>
                </div>

                <!-- Unified Pipeline Tab -->
                <div id="unified-tab" class="tab-content hidden flex flex-col gap-6">
                    <div class="glass rounded-2xl p-6 border-white/10 flex flex-col gap-4">
                        <h2 class="text-lg font-semibold text-slate-200">Unified Pipeline — Collect, Analyze &amp; Report</h2>
                        <p class="text-sm text-slate-400">
                            Orchestrates all data sources (News API, Image Processing, LLM Knowledge), runs RoBERTa sentiment analysis on every article, and generates a downloadable JSON or HTML report.
                        </p>
                        
                        <form id="unified-form" onsubmit="submitUnified(event)" enctype="multipart/form-data" class="mt-4 flex flex-col gap-5">
                            <div class="flex flex-col gap-2">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Topic / Query</label>
                                <input type="text" id="unified-topic" placeholder="e.g. Artificial Intelligence, Climate Change" class="w-full bg-[#0E1524] border border-white/10 focus:border-indigo-500/50 outline-none rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 transition-all">
                            </div>

                            <div class="flex flex-col gap-3">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Data Sources</label>
                                <div class="flex flex-wrap gap-4">
                                    <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                                        <input type="checkbox" id="unified-news" checked class="accent-indigo-500 w-4 h-4"> News API
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                                        <input type="checkbox" id="unified-llm" checked class="accent-indigo-500 w-4 h-4"> LLM Knowledge
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                                        <input type="checkbox" id="unified-img" class="accent-indigo-500 w-4 h-4" onchange="toggleUnifiedImage(this)"> Image Processing
                                    </label>
                                </div>
                            </div>

                            <div id="unified-image-zone" class="hidden flex flex-col gap-2">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Upload Image (Optional)</label>
                                <div class="border-2 border-dashed border-white/10 hover:border-indigo-500/30 rounded-xl p-6 text-center cursor-pointer transition-all relative flex flex-col items-center justify-center bg-white/[0.01]">
                                    <input type="file" id="unified-file" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer" onchange="previewUnifiedImage(event)">
                                    <div id="unified-preview-placeholder">
                                        <span class="text-3xl block mb-1">📁</span>
                                        <p class="text-xs text-indigo-400 font-medium">Click or Drag Image</p>
                                    </div>
                                    <img id="unified-image-preview" class="hidden max-h-32 rounded-lg border border-white/10" />
                                </div>
                            </div>

                            <div class="flex flex-col gap-3">
                                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Output Format</label>
                                <div class="flex gap-6">
                                    <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                                        <input type="radio" name="unified-format" value="json" checked class="accent-indigo-500 w-4 h-4"> JSON
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                                        <input type="radio" name="unified-format" value="html" class="accent-indigo-500 w-4 h-4"> HTML
                                    </label>
                                </div>
                            </div>

                            <button type="submit" id="unified-submit-btn" class="glow-btn py-3 px-6 rounded-xl text-sm font-semibold text-white mt-2">
                                🚀 Run Unified Pipeline
                            </button>
                        </form>
                    </div>
                </div>

                <!-- Shared Output Terminal -->
                <div class="mt-8">
                    <div class="glass rounded-2xl border-white/10 overflow-hidden">
                        <div class="bg-slate-900/50 px-5 py-3 border-b border-white/5 flex justify-between items-center">
                            <span class="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">Console / Output Log</span>
                            <button onclick="clearConsole()" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium">Clear Output</button>
                        </div>
                        <div id="output-screen" class="p-6 font-mono text-xs text-indigo-200 leading-relaxed bg-[#05080E] min-h-[200px] max-h-[400px] overflow-y-auto">
                            Waiting for request submission...
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <script>
            function switchTab(tabId) {
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
                document.querySelectorAll('.tab-btn').forEach(b => {
                    b.classList.remove('border-indigo-500/30', 'text-indigo-400');
                    b.classList.add('text-slate-400', 'border-white/5');
                });

                // Show selected tab
                document.getElementById(tabId).classList.remove('hidden');
                document.getElementById('btn-' + tabId).classList.add('border-indigo-500/30', 'text-indigo-400');
                document.getElementById('btn-' + tabId).classList.remove('text-slate-400', 'border-white/5');
            }

            function previewImage(event) {
                const input = event.target;
                if (input.files && input.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        document.getElementById('preview-placeholder').classList.add('hidden');
                        const img = document.getElementById('image-preview-element');
                        img.src = e.target.result;
                        img.classList.remove('hidden');
                    }
                    reader.readAsDataURL(input.files[0]);
                }
            }

            function logOutput(html) {
                document.getElementById('output-screen').innerHTML = html;
            }

            function clearConsole() {
                document.getElementById('output-screen').innerHTML = "Ready for new submission.";
            }

            async function submitImage(event) {
                event.preventDefault();
                const fileInput = document.getElementById('image-file');
                if (!fileInput.files || fileInput.files.length === 0) {
                    alert('Please select an image file first.');
                    return;
                }

                logOutput("<span class='animate-pulse text-indigo-400'>[LOG] Running Image Processing & Gemini Vision Cascade Analysis...</span>");
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                try {
                    const response = await fetch('/image-processing', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        let html = `<p class='text-emerald-400 mb-2'>✔ SUCCESS — Multimodal Analysis Complete</p>`;
                        html += `<p class='text-slate-400 mb-4'>File: ${data.filename}</p>`;
                        html += `<p class='text-slate-300 font-semibold mb-1'>[Extracted OCR Text]</p>`;
                        html += `<p class='text-slate-400 mb-4 whitespace-pre-wrap bg-white/5 p-3 rounded-lg border border-white/5'>${data.extracted_text}</p>`;
                        html += `<p class='text-indigo-300 font-semibold mb-1'>[Gemini Context News Analysis]</p>`;
                        html += `<p class='text-indigo-200 whitespace-pre-wrap bg-indigo-950/20 p-3 rounded-lg border border-indigo-500/10'>${data.news_analysis}</p>`;
                        logOutput(html);
                    } else {
                        logOutput(`<span class='text-red-400'>Error ${response.status}: ${data.detail || JSON.stringify(data)}</span>`);
                    }
                } catch (err) {
                    logOutput(`<span class='text-red-400'>Network Error: ${err.message}</span>`);
                }
            }

            async function submitNews(event) {
                event.preventDefault();
                const topic = document.getElementById('news-topic').value.trim();
                if (!topic) {
                    alert('Please enter a search topic.');
                    return;
                }

                logOutput(`<span class='animate-pulse text-indigo-400'>[LOG] Triggering ingestion API for topic: "${topic}"...</span>`);

                try {
                    const response = await fetch('/news-api', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ topic: topic })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        let html = `<p class='text-emerald-400 mb-2'>✔ SUCCESS — Topic Synced</p>`;
                        html += `<p class='text-slate-400 mb-2'>Collected Count: ${data.collected_count}</p>`;
                        html += `<p class='text-slate-400 mb-2'>Stored (New): ${data.stored_count}</p>`;
                        html += `<p class='text-slate-400 mb-4'>Duplicates Skipped: ${data.duplicates_skipped}</p>`;
                        
                        if (data.articles && data.articles.length > 0) {
                            html += `<p class='text-slate-300 font-semibold mb-2'>[Ingested Sample Articles]</p>`;
                            data.articles.forEach(art => {
                                html += `<div class='bg-white/5 border border-white/5 rounded-lg p-3 mb-2'>`;
                                html += `<p class='text-indigo-400 font-semibold'>${art.title}</p>`;
                                html += `<p class='text-slate-500 text-2xs'>Source: ${art.source} | <a href="${art.url}" target="_blank" class="text-indigo-300 underline">Link</a></p>`;
                                html += `<p class='text-slate-400 mt-1'>${art.clean_text}</p>`;
                                html += `</div>`;
                            });
                        }
                        logOutput(html);
                    } else {
                        logOutput(`<span class='text-red-400'>Error ${response.status}: ${data.detail || JSON.stringify(data)}</span>`);
                    }
                } catch (err) {
                    logOutput(`<span class='text-red-400'>Network Error: ${err.message}</span>`);
                }
            }

            async function submitLLM(event) {
                event.preventDefault();
                const query = document.getElementById('llm-query').value.trim();
                if (!query) {
                    alert('Please enter a query prompt.');
                    return;
                }

                logOutput(`<span class='animate-pulse text-indigo-400'>[LOG] Retrieving web articles & performing Gemini synthesis...</span>`);

                try {
                    const response = await fetch('/llm-knowledge', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        let html = `<p class='text-emerald-400 mb-2'>✔ SUCCESS — RAG Inference Complete</p>`;
                        if (data.context_sources && data.context_sources.length > 0) {
                            html += `<p class='text-slate-500 mb-3'>Web context sources used: ${data.context_sources.join(', ')}</p>`;
                        }
                        html += `<p class='text-slate-300 font-semibold mb-1'>[Synthesized Response]</p>`;
                        html += `<p class='text-indigo-200 whitespace-pre-wrap bg-indigo-950/20 p-4 rounded-xl border border-indigo-500/10 leading-relaxed font-sans text-sm'>${data.answer}</p>`;
                        logOutput(html);
                    } else {
                        logOutput(`<span class='text-red-400'>Error ${response.status}: ${data.detail || JSON.stringify(data)}</span>`);
                    }
                } catch (err) {
                    logOutput(`<span class='text-red-400'>Network Error: ${err.message}</span>`);
                }
            }

            // ── Unified Pipeline ──────────────────────────────────────────
            function toggleUnifiedImage(checkbox) {
                document.getElementById('unified-image-zone').classList.toggle('hidden', !checkbox.checked);
            }

            function previewUnifiedImage(event) {
                const input = event.target;
                if (input.files && input.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        document.getElementById('unified-preview-placeholder').classList.add('hidden');
                        const img = document.getElementById('unified-image-preview');
                        img.src = e.target.result;
                        img.classList.remove('hidden');
                    }
                    reader.readAsDataURL(input.files[0]);
                }
            }

            async function submitUnified(event) {
                event.preventDefault();
                const topic = document.getElementById('unified-topic').value.trim();
                if (!topic) {
                    alert('Please enter a topic.');
                    return;
                }

                const includeNews = document.getElementById('unified-news').checked;
                const includeLLM = document.getElementById('unified-llm').checked;
                const includeImage = document.getElementById('unified-img').checked;
                const outputFormat = document.querySelector('input[name="unified-format"]:checked').value;

                const btn = document.getElementById('unified-submit-btn');
                btn.disabled = true;
                btn.textContent = '⏳ Running Pipeline...';

                logOutput(`<span class='animate-pulse text-indigo-400'>[LOG] Running Unified Pipeline for topic: "${topic}"...</span><br><span class='text-slate-500'>Sources: ${includeNews ? '📰 News' : ''} ${includeLLM ? '🧠 LLM' : ''} ${includeImage ? '🖼️ Image' : ''} | Format: ${outputFormat.toUpperCase()}</span>`);

                const formData = new FormData();
                formData.append('topic', topic);
                formData.append('include_news_api', includeNews);
                formData.append('include_llm_knowledge', includeLLM);
                formData.append('include_image', includeImage);
                formData.append('output_format', outputFormat);
                formData.append('strategy', 'mean');

                if (includeImage) {
                    const fileInput = document.getElementById('unified-file');
                    if (fileInput.files && fileInput.files[0]) {
                        formData.append('file', fileInput.files[0]);
                    }
                }

                try {
                    const response = await fetch('/unified-pipeline', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        let html = `<p class='text-emerald-400 mb-3 text-base font-semibold'>✔ Pipeline Complete — ${data.total_articles_analyzed} articles analyzed in ${data.elapsed_seconds}s</p>`;

                        // Summary stats
                        const summary = data.summary || {};
                        const dist = summary.sentiment_distribution || {};
                        html += `<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;'>`;
                        html += `<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:10px 16px;min-width:100px;text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;font-weight:600;'>Dominant</div><div style='font-size:18px;font-weight:700;color:${summary.dominant_sentiment==='Positive'?'#10b981':summary.dominant_sentiment==='Negative'?'#ef4444':'#818cf8'}'>${summary.dominant_sentiment || 'N/A'}</div></div>`;
                        html += `<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:10px 16px;min-width:80px;text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;font-weight:600;'>Avg Score</div><div style='font-size:18px;font-weight:700;color:#e2e8f0'>${summary.avg_sentiment_score ?? 'N/A'}</div></div>`;
                        html += `<div style='background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.15);border-radius:10px;padding:10px 16px;text-align:center;'><div style='font-size:10px;color:#10b981;font-weight:600;'>▲ Positive</div><div style='font-size:16px;font-weight:700;color:#10b981'>${dist.Positive || 0}</div></div>`;
                        html += `<div style='background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.15);border-radius:10px;padding:10px 16px;text-align:center;'><div style='font-size:10px;color:#818cf8;font-weight:600;'>● Neutral</div><div style='font-size:16px;font-weight:700;color:#818cf8'>${dist.Neutral || 0}</div></div>`;
                        html += `<div style='background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.15);border-radius:10px;padding:10px 16px;text-align:center;'><div style='font-size:10px;color:#ef4444;font-weight:600;'>▼ Negative</div><div style='font-size:16px;font-weight:700;color:#ef4444'>${dist.Negative || 0}</div></div>`;
                        html += `</div>`;

                        // Download link
                        if (data.output_file) {
                            html += `<p class='mb-4'><a href='${data.output_file}' target='_blank' class='inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold' style='background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;text-decoration:none;'>📥 Download ${outputFormat.toUpperCase()} Report</a></p>`;
                        }

                        // Article preview (first 5)
                        const articles = data.articles || [];
                        const previewCount = Math.min(articles.length, 5);
                        if (previewCount > 0) {
                            html += `<p class='text-slate-300 font-semibold mb-2'>[Article Preview — showing ${previewCount} of ${articles.length}]</p>`;
                            for (let i = 0; i < previewCount; i++) {
                                const art = articles[i];
                                const sent = art.article_sentiment || {};
                                const sentColor = sent.label === 'Positive' ? '#10b981' : sent.label === 'Negative' ? '#ef4444' : '#818cf8';
                                html += `<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px 14px;margin-bottom:8px;'>`;
                                html += `<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;'><span style='font-weight:600;color:#e2e8f0;font-size:13px;'>${(art.title || 'Untitled').substring(0, 80)}</span><span style='font-size:11px;font-weight:600;color:${sentColor};background:${sentColor}18;padding:2px 8px;border-radius:12px;'>${sent.label || '?'} (${((sent.confidence || 0)*100).toFixed(0)}%)</span></div>`;
                                html += `<p style='font-size:11px;color:#64748b;'>Source: ${art.source || art.origin || '?'} | Score: ${art.sentiment_score ?? 'N/A'} | Intensity: ${art.emotional_intensity ?? 'N/A'}</p>`;
                                html += `</div>`;
                            }
                        }

                        logOutput(html);
                    } else {
                        logOutput(`<span class='text-red-400'>Error ${response.status}: ${data.detail || JSON.stringify(data)}</span>`);
                    }
                } catch (err) {
                    logOutput(`<span class='text-red-400'>Network Error: ${err.message}</span>`);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 Run Unified Pipeline';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
