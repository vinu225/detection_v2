# Module 1 — News Collection & Preprocessing

This module is responsible for ingesting raw news articles from external sources
and transforming them into structured, clean data objects ready for downstream
ML pipelines (e.g., Module 2 (Sentimental) — RoBERTa Sentiment Analysis).

---

## Components

| File | Responsibility |
|------|---------------|
| `config.py` | pydantic-settings configuration (API keys, DB URL, log level) |
| `news_collector.py` | Collect articles via NewsAPI, GNews, or RSS feeds |
| `scraper.py` | Fetch full article HTML from arbitrary URLs (requests → WebBaseLoader → Playwright waterfall) |
| `html_cleaner.py` | Strip scripts, ads, nav, footer, and other HTML noise |
| `content_extractor.py` | Extract and deduplicate paragraphs using Jaccard similarity |
| `preprocessing.py` | Public API — `clean_html()` and `build_clean_article()` |
| `pipeline.py` | Orchestration — `run_api_collection_pipeline()` and `run_url_collection_pipeline()` |

---

## Data Flow

```
NewsAPI / GNews / RSS
        ↓
  news_collector.py  →  List[RawArticle]
        ↓
  preprocessing.py   →  CleanArticle
        ↓
  shared/database.py →  MongoDB (articles collection)
```

---

## Tests

```bash
pytest module_1_scraping/tests/ -v
```

---

## Configuration

All settings are loaded from the `.env` file in the project root.

| Env Variable | Default | Description |
|---|---|---|
| `NEWS_API_KEY` | `""` | NewsAPI.org API key |
| `GNEWS_API_KEY` | `""` | GNews.io API key |
| `DATABASE_URL` | `mongodb://localhost:27017/news_detection` | MongoDB connection string |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `logs/app.log` | Log file path |
| `SCRAPER_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `SCRAPER_MAX_RETRIES` | `3` | Number of retry attempts |
| `SCRAPER_RATE_LIMIT_DELAY` | `1.0` | Base delay between retries (seconds) |
| `RSS_FEEDS` | `""` | Comma-separated list of RSS feed URLs |
