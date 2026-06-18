"""
shared/constants.py — Project-wide constants shared across all modules.
"""

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_DEFAULT_DB = "news_detection"
MONGO_ARTICLES_COLLECTION = "articles"
MONGO_POOL_SIZE_MAX = 15
MONGO_POOL_SIZE_MIN = 5
MONGO_SERVER_SELECTION_TIMEOUT_MS = 5000

# ── Scraper ───────────────────────────────────────────────────────────────────
SCRAPER_MIN_CONTENT_LENGTH = 200   # chars; below this, richer strategy is tried
SCRAPER_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ── Preprocessing ─────────────────────────────────────────────────────────────
MIN_PARAGRAPH_WORDS = 8    # paragraphs shorter than this are discarded
MAX_DUPLICATE_RATIO = 0.8  # Jaccard ratio above which a paragraph is a duplicate

# ── News providers ────────────────────────────────────────────────────────────
NEWSAPI_CATEGORIES = {
    "business", "entertainment", "general", "health",
    "science", "sports", "technology",
}
GNEWS_CATEGORIES = {
    "general", "world", "nation", "business", "technology",
    "entertainment", "sports", "science", "health",
}
SUPPORTED_PROVIDERS = {"newsapi", "gnews", "rss"}
