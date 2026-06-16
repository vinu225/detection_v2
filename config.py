"""
config.py — Centralized application configuration via pydantic-settings.
All values are loaded from environment variables or the .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    # ── API keys ────────────────────────────────────────────────────────────
    news_api_key: str = Field(default="", alias="NEWS_API_KEY")
    gnews_api_key: str = Field(default="", alias="GNEWS_API_KEY")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="mongodb://localhost:27017/news_detection",
        alias="DATABASE_URL",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", alias="LOG_FILE")

    # ── Scraper ───────────────────────────────────────────────────────────────
    scraper_timeout: int = Field(default=30, alias="SCRAPER_TIMEOUT")
    scraper_max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")
    scraper_rate_limit_delay: float = Field(default=1.0, alias="SCRAPER_RATE_LIMIT_DELAY")

    # ── RSS ───────────────────────────────────────────────────────────────────
    rss_feeds: str = Field(default="", alias="RSS_FEEDS")

    @property
    def rss_feed_list(self) -> List[str]:
        return [f.strip() for f in self.rss_feeds.split(",") if f.strip()]

    model_config = {
        "env_file": ".env",
        "populate_by_name": True,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
