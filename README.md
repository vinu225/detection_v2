# News Collection & Preprocessing Pipeline

A production-ready FastAPI service that ingests news articles from APIs and websites,
cleans the HTML, structures the content, and exposes it for downstream ML pipelines.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI (app.py)                             │
│  POST /collect/api  POST /collect/url  POST /clean  POST /store     │
│  GET  /article/{id} GET  /articles    DELETE /article/{id}          │
└────────────┬────────────────┬──────────────────┬────────────────────┘
             │                │                  │
   ┌─────────▼──────┐  ┌──────▼──────┐  ┌───────▼────────┐
   │ news_collector │  │   scraper   │  │ preprocessor   │
   │   NewsAPI      │  │  requests   │  │  BS4 cleaning  │
   │   GNews        │  │  BS4        │  │  normalization │
   │   RSS/Atom     │  │  WebBase    │  │  deduplication │
   └─────────┬──────┘  │  Playwright │  └───────┬────────┘
             │         └─────────────┘          │
             └──────────────────────────────────┘
                                │
                       ┌────────▼────────┐
                       │   database.py   │
                       │   PostgreSQL    │
                       │   SQLAlchemy    │
                       └─────────────────┘
```

---

## Quick Start

### 1. Clone & install

```bash
git clone <repo>
cd news_pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # only needed for JS-rendered sites
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and database URL
```

### 3. Start PostgreSQL

```bash
docker run -d \
  --name news-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=news_db \
  -p 5432:5432 \
  postgres:16
```

### 4. Run the API

```bash
uvicorn app:app --reload
```

API docs available at: **http://localhost:8000/docs**

---

## File Structure

```
news_pipeline/
├── app.py              ← FastAPI application + all endpoints
├── config.py           ← Settings via pydantic-settings (.env)
├── database.py         ← SQLAlchemy ORM, CRUD, duplicate detection
├── models.py           ← Pydantic schemas (request/response/internal)
├── news_collector.py   ← NewsAPI / GNews / RSS collection
├── preprocessor.py     ← HTML cleaning + structured article generation
├── scraper.py          ← requests / WebBaseLoader / Playwright scraping
├── logger.py           ← Rotating file + console logger
├── requirements.txt
├── .env.example
├── logs/               ← Created automatically
│   └── app.log
└── tests/
    └── test_pipeline.py
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NEWS_API_KEY` | Optional | [newsapi.org](https://newsapi.org) key |
| `GNEWS_API_KEY` | Optional | [gnews.io](https://gnews.io) key |
| `DATABASE_URL` | **Yes** | `postgresql://user:pass@host:port/db` |
| `RSS_FEEDS` | Optional | Comma-separated RSS feed URLs |
| `SCRAPER_TIMEOUT` | Optional | HTTP timeout in seconds (default 30) |
| `SCRAPER_MAX_RETRIES` | Optional | Retry attempts (default 3) |
| `LOG_LEVEL` | Optional | `DEBUG` / `INFO` / `WARNING` (default INFO) |

---

## API Reference

### `POST /collect/api` — Collect from a News API

```json
{
  "provider": "newsapi",        // "newsapi" | "gnews" | "rss"
  "query": "artificial intelligence",
  "category": "technology",
  "source": "bbc-news",
  "from_date": "2024-01-01",
  "to_date": "2024-12-31",
  "page": 1,
  "page_size": 20
}
```

Response:
```json
{
  "success": true,
  "collected": 20,
  "stored": 18,
  "duplicates": 2,
  "articles": [ ... ],
  "errors": []
}
```

---

### `POST /collect/url` — Scrape a single URL

```json
{
  "url": "https://www.bbc.com/news/article-123",
  "use_playwright": false
}
```

Set `use_playwright: true` for JavaScript-rendered (SPA) sites.

---

### `POST /clean` — Clean raw HTML (no storage)

```json
{
  "html": "<html>...</html>",
  "url": "https://example.com"   // optional, for context
}
```

Response:
```json
{
  "success": true,
  "clean_text": "Article body text …",
  "word_count": 432,
  "paragraphs": ["Para one …", "Para two …"]
}
```

---

### `POST /store` — Store a pre-processed article

```json
{
  "article": {
    "article_id": "...",
    "title": "...",
    "url": "...",
    "clean_text": "...",
    "content_hash": "...",
    "url_hash": "..."
  }
}
```

---

### `GET /article/{id}` — Retrieve by UUID

```
GET /article/550e8400-e29b-41d4-a716-446655440000
```

---

### `GET /articles?skip=0&limit=50` — Paginated list

For ML pipeline bulk consumption.

---

### `DELETE /article/{id}` — Delete

---

### `GET /health` — Health check

```json
{
  "status": "ok",
  "database": "ok",
  "timestamp": "2024-06-01T12:00:00"
}
```

---

## Preprocessing Pipeline

Every article goes through the following stages:

1. **Noise removal** — scripts, styles, ads, navbars, footers, cookie banners, social widgets, comments, paywalls
2. **Unicode normalization** — NFKC, smart quotes → straight, ligatures → ASCII
3. **Whitespace normalization** — collapse runs, strip trailing spaces per line
4. **Paragraph extraction** — split on blank lines
5. **Short paragraph filter** — drop paragraphs < 8 words
6. **Duplicate paragraph filter** — Jaccard similarity deduplication (≥ 0.8 threshold)
7. **Hash generation** — SHA-256 of content and URL for database deduplication

---

## Duplicate Detection

Two layers:
- **URL hash** — same URL is never scraped twice
- **Content hash** — same text stored under a different URL is skipped

Both hashes are stored as unique-indexed columns; database-level uniqueness constraints prevent race conditions.

---

## Scraping Strategy (Waterfall)

1. **requests + BeautifulSoup** — fast, low overhead (~80 % of sites)
2. **LangChain WebBaseLoader** — more robust parsing for structured sites
3. **LangChain PlaywrightURLLoader** — full JS rendering for SPAs (Chromium headless)

Auto-fallback triggers when extracted content is < 200 characters.

---

## Running Tests

```bash
pytest tests/ -v
```

22 unit tests covering preprocessor, model validation, and hash utilities.

---

## Notes for ML Pipelines

- Use `GET /articles?skip=N&limit=50` to paginate over all stored articles.
- `clean_text` is the ready-to-tokenize body; `paragraphs` provides sentence-level structure.
- `content_hash` can be used as a stable feature ID.
- `word_count` enables quick length-based filtering before inference.
