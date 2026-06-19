"""
pipeline_orchestrator.py — Unified pipeline orchestrator.

Wires all three data sources (image-processing, news-api, llm-knowledge)
into the RoBERTa sentiment analysis model and produces JSON or HTML report files.

Public API:
    run_unified_pipeline(...)  → UnifiedPipelineResult
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pymongo.database import Database

from module_1_scraping.image_processing import (
    analyze_image_news_context,
    query_gemini_text,
)
from module_1_scraping.news_collector import collect_articles
from module_1_scraping.preprocessing import build_clean_article
from module_2_sentimental.pipeline import SentimentPipeline
from shared.database import store_article
from shared.logger import get_logger
from shared.models import RawArticle

log = get_logger("pipeline_orchestrator")

# Output directory — relative to project root
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Maximum articles to process through sentiment analysis per run
MAX_ARTICLES = 50


# ─────────────────────────────────────────────────────────────────────────────
# Result Container
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedPipelineResult:
    """Container for the unified pipeline output."""

    def __init__(self):
        self.topic: str = ""
        self.total_articles: int = 0
        self.sources_used: List[str] = []
        self.output_format: str = "json"
        self.output_filename: str = ""
        self.stages: Dict[str, Any] = {}
        self.articles: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}
        self.elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": True,
            "topic": self.topic,
            "total_articles_analyzed": self.total_articles,
            "sources_used": self.sources_used,
            "output_format": self.output_format,
            "output_file": f"/output/{self.output_filename}",
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "summary": self.summary,
            "stages": self.stages,
            "articles": self.articles,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: News API Collection
# ─────────────────────────────────────────────────────────────────────────────

import re as _re

def _extract_search_keywords(topic: str) -> str:
    """
    Strip natural-language filler words and return a clean keyword query
    suitable for news API searches.
    e.g. "recent news about the iran war ?" -> "iran war"
    """
    cleaned = topic.lower()
    # Remove trailing punctuation
    cleaned = cleaned.rstrip("?!.,;:")
    # Remove common filler phrases
    filler = r"\b(recent|news|about|the|what|is|are|of|who|info|for|on|tell|me|give|latest|today|current|happening|regarding|related|update|updates|in|and|or|a|an)\b"
    cleaned = _re.sub(filler, " ", cleaned)
    # Collapse whitespace
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    # Fall back to original topic if cleaning made it empty
    return cleaned if len(cleaned) >= 3 else topic.strip("?!., ")


def _collect_news_articles(
    topic: str,
    db: Optional[Database] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Collects articles from all news providers (NewsAPI, GNews, RSS, Search),
    preprocesses them, and optionally stores in MongoDB.
    Returns (article_dicts, stage_metadata).
    """
    # Clean up natural-language queries into short keyword phrases for APIs
    search_query = _extract_search_keywords(topic)
    log.info("Stage 1 — topic=%r → search_query=%r", topic, search_query)

    providers = ["gnews", "newsapi", "rss", "search"]
    all_raw = []
    provider_counts = {}

    for p in providers:
        try:
            log.info("Stage 1 — querying provider: %s for topic: %r", p, search_query)
            articles = collect_articles(provider=p, query=search_query, page_size=10)
            provider_counts[p] = len(articles)
            all_raw.extend(articles)
        except Exception as exc:
            log.warning("Provider %s failed: %s", p, exc)
            provider_counts[p] = 0


    # Preprocess and deduplicate
    article_dicts = []
    stored_count = 0
    seen_urls = set()

    for raw in all_raw:
        if raw.url in seen_urls:
            continue
        seen_urls.add(raw.url)

        try:
            clean = build_clean_article(raw)

            # Store in MongoDB if database is available
            if db is not None:
                try:
                    _, is_new = store_article(db, clean)
                    if is_new:
                        stored_count += 1
                except Exception as exc:
                    log.warning("DB store skipped: %s", exc)

            article_dicts.append({
                "article_id": clean.article_id,
                "title": clean.title,
                "author": clean.author,
                "source": clean.source or "News API",
                "url": clean.url,
                "publication_date": clean.publication_date,
                "clean_text": clean.clean_text,
                "content": clean.clean_text,
                "origin": "news-api",
            })
        except Exception as exc:
            log.error("Article preprocessing failed for %s: %s", raw.url, exc)

    stage_meta = {
        "providers_queried": providers,
        "provider_counts": provider_counts,
        "total_collected": len(all_raw),
        "deduplicated": len(article_dicts),
        "stored_to_db": stored_count,
    }

    log.info(
        "Stage 1 complete: collected=%d deduplicated=%d stored=%d",
        len(all_raw), len(article_dicts), stored_count,
    )
    return article_dicts, stage_meta


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Image Processing
# ─────────────────────────────────────────────────────────────────────────────

def _process_image_source(
    image_bytes: bytes,
    filename: str = "image.png",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Runs OCR + contextual analysis on the uploaded image.
    Packages the result as a synthetic article dict for sentiment analysis.
    Returns (article_dict, stage_metadata).
    """
    log.info("Stage 2 — processing image: %s (%d bytes)", filename, len(image_bytes))

    results = analyze_image_news_context(image_bytes, filename=filename)

    extracted_text = results.get("extracted_text", "")
    news_analysis = results.get("news_analysis", "")

    # Combine OCR text and analysis into a single article body
    combined_text = extracted_text
    if news_analysis:
        combined_text += "\n\n--- Contextual Analysis ---\n\n" + news_analysis

    article_dict = {
        "article_id": f"img_{uuid.uuid4().hex[:12]}",
        "title": f"Image Analysis — {filename}",
        "author": "Gemini Vision Processor",
        "source": "Uploaded Image",
        "url": f"image://{filename}",
        "publication_date": datetime.now(timezone.utc).isoformat(),
        "clean_text": combined_text,
        "content": combined_text,
        "origin": "image-processing",
        "image_ocr_text": extracted_text,
        "image_news_analysis": news_analysis,
    }

    stage_meta = {
        "filename": filename,
        "image_size_bytes": len(image_bytes),
        "ocr_text_length": len(extracted_text),
        "analysis_length": len(news_analysis),
    }

    log.info("Stage 2 complete: OCR=%d chars, analysis=%d chars", len(extracted_text), len(news_analysis))
    return article_dict, stage_meta


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: LLM Knowledge (Web Scraping + Gemini Synthesis)
# ─────────────────────────────────────────────────────────────────────────────

def _run_llm_knowledge(topic: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Scrapes the web for live context on the topic, feeds it to Gemini
    for synthesis, and packages the response as a synthetic article dict.
    Returns (article_dict, stage_metadata).
    """
    log.info("Stage 3 — LLM knowledge synthesis for topic: %r", topic)

    # Extract query keywords (same heuristic as the existing /llm-knowledge endpoint)
    clean_query = topic.lower()
    clean_query = re.sub(
        r"\b(what|is|are|the|recent|news|about|of|who|info|for|on)\b",
        "", clean_query,
    )
    keywords = [kw.strip() for kw in clean_query.split() if len(kw.strip()) > 2]
    search_topic = " ".join(keywords) if keywords else topic

    # Retrieve web context via search scraping
    context_builder = []
    retrieved_sources = []

    queries_to_search = [
        search_topic,
        f"{search_topic} reddit",
        f"{search_topic} twitter",
    ]

    for q in queries_to_search:
        try:
            articles = collect_articles(provider="search", query=q, page_size=4)
            for art in articles:
                content = art.content or art.description or ""
                if len(content) > 10:
                    context_builder.append(
                        f"Source: {art.source or 'Web'}\n"
                        f"Title: {art.title}\n"
                        f"Content: {content[:800]}\n"
                    )
                    retrieved_sources.append(art.source or "Web")
        except Exception as exc:
            log.warning("Web context search failed for %r: %s", q, exc)

    # Fallback to RSS if web search returned nothing
    if not context_builder:
        try:
            articles = collect_articles(provider="rss", query=search_topic, page_size=8)
            for art in articles:
                content = art.content or art.description or ""
                if len(content) > 10:
                    context_builder.append(
                        f"Source: {art.source or 'RSS'}\n"
                        f"Title: {art.title}\n"
                        f"Content: {content[:800]}\n"
                    )
                    retrieved_sources.append(art.source or "RSS Feed")
        except Exception as exc:
            log.warning("RSS fallback failed: %s", exc)

    context_str = "\n---\n".join(context_builder) if context_builder else "No external web articles found."

    # Formulate prompt for Gemini
    system_prompt = (
        "You are an advanced news synthesis agent. Your task is to answer the user's question "
        "comprehensively. Use both your own knowledge and the provided live web scraped search context "
        "to construct a detailed, factual, and informative response.\n\n"
        f"User Question: {topic}\n\n"
        "Retrieved Web Context (including news, blogs, and social platforms):\n"
        f"{context_str}\n\n"
        "Please provide a well-structured answer, citing sources if relevant. Avoid making up facts."
    )

    # Generate answer via Gemini
    try:
        answer = query_gemini_text(system_prompt)
    except Exception as exc:
        log.error("Gemini synthesis failed: %s", exc)
        answer = f"LLM synthesis was unavailable: {exc}"

    article_dict = {
        "article_id": f"llm_{uuid.uuid4().hex[:12]}",
        "title": f"LLM Synthesis — {topic}",
        "author": "Gemini Synthesis Agent",
        "source": "LLM Knowledge",
        "url": f"llm://{uuid.uuid4().hex[:8]}",
        "publication_date": datetime.now(timezone.utc).isoformat(),
        "clean_text": answer,
        "content": answer,
        "origin": "llm-knowledge",
        "context_sources": list(set(retrieved_sources)),
    }

    stage_meta = {
        "search_topic": search_topic,
        "context_sources_count": len(set(retrieved_sources)),
        "context_sources": list(set(retrieved_sources)),
        "answer_length": len(answer),
    }

    log.info("Stage 3 complete: sources=%d answer=%d chars", len(set(retrieved_sources)), len(answer))
    return article_dict, stage_meta


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Sentiment Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _run_sentiment_analysis(
    articles: List[Dict[str, Any]],
    strategy: str = "mean",
) -> List[Dict[str, Any]]:
    """
    Initializes the SentimentPipeline singleton and runs sentiment analysis
    on every article dict. Returns enriched article dicts with sentiment fields.
    """
    if not articles:
        log.warning("Stage 4 — no articles to analyze.")
        return []

    log.info("Stage 4 — running sentiment analysis on %d articles (strategy=%s)", len(articles), strategy)

    pipeline = SentimentPipeline()
    enriched = []

    for idx, article in enumerate(articles):
        try:
            sentiment_result = pipeline.process_article_data(article, strategy=strategy)

            # Merge original article metadata with sentiment results
            merged = {**article, **sentiment_result}
            enriched.append(merged)
            log.debug(
                "Article %d/%d (%s) → %s (%.2f)",
                idx + 1, len(articles),
                article.get("title", "?")[:40],
                sentiment_result.get("article_sentiment", {}).get("label", "?"),
                sentiment_result.get("article_sentiment", {}).get("confidence", 0),
            )
        except Exception as exc:
            log.error("Sentiment analysis failed for article %d (%s): %s", idx, article.get("title", "?"), exc)
            # Include the article with an error marker
            article["sentiment_error"] = str(exc)
            enriched.append(article)

    log.info("Stage 4 complete: %d/%d articles enriched with sentiment.", len(enriched), len(articles))
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: Report Generation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_summary(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics from enriched articles."""
    total = len(articles)
    if total == 0:
        return {"total": 0}

    sentiments = {"Positive": 0, "Negative": 0, "Neutral": 0}
    scores = []
    intensities = []
    reliabilities = []

    for art in articles:
        body_sent = art.get("article_sentiment", {})
        label = body_sent.get("label", "Neutral")
        sentiments[label] = sentiments.get(label, 0) + 1

        if "sentiment_score" in art:
            scores.append(art["sentiment_score"])
        if "emotional_intensity" in art:
            intensities.append(art["emotional_intensity"])
        if "sentiment_reliability" in art:
            reliabilities.append(art["sentiment_reliability"])

    summary = {
        "total_articles": total,
        "sentiment_distribution": sentiments,
        "dominant_sentiment": max(sentiments, key=sentiments.get),
    }

    if scores:
        summary["avg_sentiment_score"] = round(sum(scores) / len(scores), 2)
    if intensities:
        summary["avg_emotional_intensity"] = round(sum(intensities) / len(intensities), 2)
    if reliabilities:
        summary["avg_reliability"] = round(sum(reliabilities) / len(reliabilities), 2)

    # Per-origin breakdown
    origins = {}
    for art in articles:
        origin = art.get("origin", "unknown")
        if origin not in origins:
            origins[origin] = 0
        origins[origin] += 1
    summary["articles_by_source"] = origins

    return summary


def _generate_filename(topic: str, fmt: str) -> str:
    """Generate a timestamped report filename."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())[:30].strip("_")
    return f"report_{ts}_{slug}.{fmt}"


def _generate_json_report(
    articles: List[Dict[str, Any]],
    topic: str,
    summary: Dict[str, Any],
    stages: Dict[str, Any],
    elapsed: float,
) -> str:
    """Write the JSON report file. Returns the filename."""
    filename = _generate_filename(topic, "json")
    filepath = OUTPUT_DIR / filename

    report = {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "total_articles": len(articles),
            "elapsed_seconds": round(elapsed, 2),
            "format": "json",
        },
        "summary": summary,
        "stages": stages,
        "articles": articles,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    log.info("JSON report written: %s (%d bytes)", filepath, filepath.stat().st_size)
    return filename


def _generate_html_report(
    articles: List[Dict[str, Any]],
    topic: str,
    summary: Dict[str, Any],
    stages: Dict[str, Any],
    elapsed: float,
) -> str:
    """Write a styled HTML report file. Returns the filename."""
    filename = _generate_filename(topic, "html")
    filepath = OUTPUT_DIR / filename

    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    dist = summary.get("sentiment_distribution", {})
    pos_count = dist.get("Positive", 0)
    neg_count = dist.get("Negative", 0)
    neu_count = dist.get("Neutral", 0)
    total = summary.get("total_articles", 0)
    dominant = summary.get("dominant_sentiment", "N/A")
    avg_score = summary.get("avg_sentiment_score", "N/A")
    avg_intensity = summary.get("avg_emotional_intensity", "N/A")
    avg_reliability = summary.get("avg_reliability", "N/A")

    # Build article cards
    article_cards = []
    for idx, art in enumerate(articles):
        body_sent = art.get("article_sentiment", {})
        hl_sent = art.get("headline_sentiment", {})
        label = body_sent.get("label", "N/A")
        conf = body_sent.get("confidence", 0)
        score = art.get("sentiment_score", "N/A")
        intensity = art.get("emotional_intensity", "N/A")
        reliability = art.get("sentiment_reliability", "N/A")
        origin = art.get("origin", "unknown")

        # Color coding
        if label == "Positive":
            badge_color = "#10b981"
            badge_bg = "rgba(16, 185, 129, 0.12)"
        elif label == "Negative":
            badge_color = "#ef4444"
            badge_bg = "rgba(239, 68, 68, 0.12)"
        else:
            badge_color = "#6366f1"
            badge_bg = "rgba(99, 102, 241, 0.12)"

        # Origin badge
        origin_colors = {
            "news-api": ("#06b6d4", "rgba(6, 182, 212, 0.12)"),
            "image-processing": ("#f59e0b", "rgba(245, 158, 11, 0.12)"),
            "llm-knowledge": ("#8b5cf6", "rgba(139, 92, 246, 0.12)"),
        }
        o_color, o_bg = origin_colors.get(origin, ("#94a3b8", "rgba(148, 163, 184, 0.12)"))

        title = art.get("title", "Untitled")
        source = art.get("source", "Unknown")
        url = art.get("url", "#")
        text_preview = (art.get("clean_text", "") or "")[:400]
        if len(art.get("clean_text", "")) > 400:
            text_preview += "…"

        # Probability bars
        neg_prob = body_sent.get("negative_probability", 0)
        neu_prob = body_sent.get("neutral_probability", 0)
        pos_prob = body_sent.get("positive_probability", 0)

        card = f"""
        <div class="article-card">
            <div class="card-header">
                <div class="card-badges">
                    <span class="badge" style="color:{badge_color};background:{badge_bg};border:1px solid {badge_color}22">
                        {label} ({conf:.1%})
                    </span>
                    <span class="badge" style="color:{o_color};background:{o_bg};border:1px solid {o_color}22">
                        {origin}
                    </span>
                </div>
                <span class="card-index">#{idx + 1}</span>
            </div>
            <h3 class="card-title">{title}</h3>
            <p class="card-meta">Source: {source} {f'&middot; <a href="{url}" target="_blank">Link</a>' if url.startswith("http") else ""}</p>
            <p class="card-text">{text_preview}</p>
            <div class="prob-bars">
                <div class="prob-row">
                    <span class="prob-label">Negative</span>
                    <div class="prob-bar-track"><div class="prob-bar prob-neg" style="width:{neg_prob*100:.1f}%"></div></div>
                    <span class="prob-val">{neg_prob:.1%}</span>
                </div>
                <div class="prob-row">
                    <span class="prob-label">Neutral</span>
                    <div class="prob-bar-track"><div class="prob-bar prob-neu" style="width:{neu_prob*100:.1f}%"></div></div>
                    <span class="prob-val">{neu_prob:.1%}</span>
                </div>
                <div class="prob-row">
                    <span class="prob-label">Positive</span>
                    <div class="prob-bar-track"><div class="prob-bar prob-pos" style="width:{pos_prob*100:.1f}%"></div></div>
                    <span class="prob-val">{pos_prob:.1%}</span>
                </div>
            </div>
            <div class="card-scores">
                <div class="score-chip"><span class="score-label">Score</span><span class="score-val">{score}</span></div>
                <div class="score-chip"><span class="score-label">Intensity</span><span class="score-val">{intensity}</span></div>
                <div class="score-chip"><span class="score-label">Reliability</span><span class="score-val">{reliability}</span></div>
            </div>
        </div>
        """
        article_cards.append(card)

    cards_html = "\n".join(article_cards)

    # Origin counts for stage summary
    stages_html = ""
    for stage_name, stage_data in stages.items():
        items = "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in stage_data.items() if not isinstance(v, (list, dict)))
        stages_html += f'<div class="stage-box"><h4>{stage_name}</h4><ul>{items}</ul></div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pipeline Report — {topic}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: #0a0e1a;
            color: #e2e8f0;
            line-height: 1.6;
            padding: 0;
        }}
        .report-header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 50%, #042f2e 100%);
            padding: 48px 40px 40px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .report-header h1 {{
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(90deg, #e2e8f0, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }}
        .report-header .subtitle {{
            font-size: 13px;
            color: #64748b;
            font-weight: 400;
        }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }}
        .summary-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 20px;
            backdrop-filter: blur(12px);
        }}
        .summary-card .sc-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #64748b;
            margin-bottom: 6px;
        }}
        .summary-card .sc-value {{
            font-size: 26px;
            font-weight: 700;
            color: #f1f5f9;
        }}
        .summary-card .sc-value.positive {{ color: #10b981; }}
        .summary-card .sc-value.negative {{ color: #ef4444; }}
        .summary-card .sc-value.neutral {{ color: #6366f1; }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #cbd5e1;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .stages-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 32px; }}
        .stage-box {{
            flex: 1;
            min-width: 220px;
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 16px;
        }}
        .stage-box h4 {{
            font-size: 13px;
            font-weight: 600;
            color: #818cf8;
            margin-bottom: 8px;
            text-transform: capitalize;
        }}
        .stage-box ul {{ list-style: none; font-size: 12px; color: #94a3b8; }}
        .stage-box li {{ margin-bottom: 3px; }}
        .stage-box li strong {{ color: #cbd5e1; }}
        .article-card {{
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 16px;
            transition: border-color 0.2s;
        }}
        .article-card:hover {{ border-color: rgba(99, 102, 241, 0.25); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .card-badges {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .badge {{
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
            letter-spacing: 0.02em;
        }}
        .card-index {{ font-size: 12px; color: #475569; font-weight: 500; }}
        .card-title {{ font-size: 16px; font-weight: 600; color: #e2e8f0; margin-bottom: 4px; }}
        .card-meta {{ font-size: 12px; color: #64748b; margin-bottom: 10px; }}
        .card-meta a {{ color: #818cf8; text-decoration: none; }}
        .card-meta a:hover {{ text-decoration: underline; }}
        .card-text {{
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.65;
            margin-bottom: 16px;
            background: rgba(255,255,255,0.02);
            padding: 12px 14px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.03);
        }}
        .prob-bars {{ margin-bottom: 14px; }}
        .prob-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }}
        .prob-label {{ font-size: 11px; color: #64748b; width: 62px; text-align: right; flex-shrink: 0; }}
        .prob-bar-track {{
            flex: 1;
            height: 7px;
            background: rgba(255,255,255,0.04);
            border-radius: 4px;
            overflow: hidden;
        }}
        .prob-bar {{ height: 100%; border-radius: 4px; transition: width 0.4s ease; }}
        .prob-neg {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
        .prob-neu {{ background: linear-gradient(90deg, #6366f1, #818cf8); }}
        .prob-pos {{ background: linear-gradient(90deg, #10b981, #34d399); }}
        .prob-val {{ font-size: 11px; color: #94a3b8; width: 42px; text-align: right; flex-shrink: 0; }}
        .card-scores {{ display: flex; gap: 10px; }}
        .score-chip {{
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 8px 16px;
            min-width: 80px;
        }}
        .score-label {{ font-size: 10px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
        .score-val {{ font-size: 18px; font-weight: 700; color: #e2e8f0; }}
        .footer {{
            text-align: center;
            padding: 32px;
            font-size: 12px;
            color: #475569;
            border-top: 1px solid rgba(255,255,255,0.04);
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="report-header">
        <div style="max-width:1100px;margin:0 auto;">
            <h1>AetherNews — Pipeline Analysis Report</h1>
            <p class="subtitle">Topic: "{topic}" &middot; Generated {generated_at} &middot; {total} articles analyzed in {elapsed:.1f}s</p>
        </div>
    </div>
    <div class="container">
        <div class="summary-grid">
            <div class="summary-card">
                <div class="sc-label">Total Articles</div>
                <div class="sc-value">{total}</div>
            </div>
            <div class="summary-card">
                <div class="sc-label">Dominant Sentiment</div>
                <div class="sc-value {'positive' if dominant == 'Positive' else 'negative' if dominant == 'Negative' else 'neutral'}">{dominant}</div>
            </div>
            <div class="summary-card">
                <div class="sc-label">Avg Score</div>
                <div class="sc-value">{avg_score}</div>
            </div>
            <div class="summary-card">
                <div class="sc-label">Avg Intensity</div>
                <div class="sc-value">{avg_intensity}</div>
            </div>
            <div class="summary-card">
                <div class="sc-label">Avg Reliability</div>
                <div class="sc-value">{avg_reliability}</div>
            </div>
            <div class="summary-card">
                <div class="sc-label">Sentiment Breakdown</div>
                <div style="font-size:13px;margin-top:4px;">
                    <span style="color:#10b981">▲ {pos_count} Positive</span><br>
                    <span style="color:#6366f1">● {neu_count} Neutral</span><br>
                    <span style="color:#ef4444">▼ {neg_count} Negative</span>
                </div>
            </div>
        </div>

        <h2 class="section-title">Pipeline Stages</h2>
        <div class="stages-row">
            {stages_html}
        </div>

        <h2 class="section-title">Article Analysis ({total} articles)</h2>
        {cards_html}
    </div>
    <div class="footer">
        AetherNews Unified Pipeline &middot; Powered by RoBERTa Sentiment + Gemini Vision + Multi-Source Ingestion
    </div>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    log.info("HTML report written: %s (%d bytes)", filepath, filepath.stat().st_size)
    return filename


# ─────────────────────────────────────────────────────────────────────────────
# Main Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_unified_pipeline(
    topic: str,
    db: Optional[Database] = None,
    image_bytes: Optional[bytes] = None,
    image_filename: str = "image.png",
    include_news_api: bool = True,
    include_llm_knowledge: bool = True,
    include_image: bool = False,
    output_format: str = "json",
    strategy: str = "mean",
) -> UnifiedPipelineResult:
    """
    Main orchestrator: collects articles from all enabled sources,
    runs sentiment analysis, and generates the output report.
    """
    start = time.perf_counter()
    result = UnifiedPipelineResult()
    result.topic = topic
    result.output_format = output_format

    all_articles: List[Dict[str, Any]] = []
    sources_used: List[str] = []
    stages: Dict[str, Any] = {}

    # ── Stage 1: News API ─────────────────────────────────────────────────
    if include_news_api:
        try:
            news_articles, news_meta = _collect_news_articles(topic, db=db)
            all_articles.extend(news_articles)
            sources_used.append("news-api")
            stages["news_api"] = news_meta
        except Exception as exc:
            log.error("Stage 1 (News API) failed: %s", exc)
            stages["news_api"] = {"error": str(exc)}

    # ── Stage 2: Image Processing ─────────────────────────────────────────
    if include_image and image_bytes:
        try:
            img_article, img_meta = _process_image_source(image_bytes, image_filename)
            all_articles.append(img_article)
            sources_used.append("image-processing")
            stages["image_processing"] = img_meta
        except Exception as exc:
            log.error("Stage 2 (Image Processing) failed: %s", exc)
            stages["image_processing"] = {"error": str(exc)}

    # ── Stage 3: LLM Knowledge ────────────────────────────────────────────
    if include_llm_knowledge:
        try:
            llm_article, llm_meta = _run_llm_knowledge(topic)
            all_articles.append(llm_article)
            sources_used.append("llm-knowledge")
            stages["llm_knowledge"] = llm_meta
        except Exception as exc:
            log.error("Stage 3 (LLM Knowledge) failed: %s", exc)
            stages["llm_knowledge"] = {"error": str(exc)}

    # ── Cap article count ─────────────────────────────────────────────────
    if len(all_articles) > MAX_ARTICLES:
        log.warning(
            "Capping articles from %d to %d for sentiment analysis.",
            len(all_articles), MAX_ARTICLES,
        )
        all_articles = all_articles[:MAX_ARTICLES]

    # ── Stage 4: Sentiment Analysis ───────────────────────────────────────
    try:
        enriched_articles = _run_sentiment_analysis(all_articles, strategy=strategy)
        stages["sentiment_analysis"] = {
            "articles_processed": len(enriched_articles),
            "strategy": strategy,
        }
    except Exception as exc:
        log.error("Stage 4 (Sentiment Analysis) failed: %s", exc)
        enriched_articles = all_articles
        stages["sentiment_analysis"] = {"error": str(exc)}

    # ── Compute summary ───────────────────────────────────────────────────
    summary = _compute_summary(enriched_articles)
    elapsed = time.perf_counter() - start

    # ── Stage 5: Generate Report ──────────────────────────────────────────
    try:
        if output_format == "html":
            filename = _generate_html_report(enriched_articles, topic, summary, stages, elapsed)
        else:
            filename = _generate_json_report(enriched_articles, topic, summary, stages, elapsed)

        # Also always generate the JSON companion for HTML reports
        if output_format == "html":
            _generate_json_report(enriched_articles, topic, summary, stages, elapsed)

        result.output_filename = filename
    except Exception as exc:
        log.error("Stage 5 (Report Generation) failed: %s", exc)
        result.output_filename = ""

    # ── Assemble result ───────────────────────────────────────────────────
    result.total_articles = len(enriched_articles)
    result.sources_used = sources_used
    result.stages = stages
    result.articles = enriched_articles
    result.summary = summary
    result.elapsed_seconds = elapsed

    log.info(
        "Unified pipeline complete: topic=%r articles=%d sources=%s elapsed=%.2fs",
        topic, result.total_articles, sources_used, elapsed,
    )
    return result
