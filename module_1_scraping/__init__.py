"""
module_1 — News Collection & Web Scraping pipeline.

Exposes:
  - config:          application settings (pydantic-settings)
  - news_collector:  NewsAPI / GNews / RSS ingestion
  - scraper:         URL content downloader (requests → WebBaseLoader → Playwright)
  - html_cleaner:    noise-tag removal and HTML comment stripping
  - content_extractor: paragraph extraction, dedup, Jaccard similarity
  - preprocessing:   public API (build_clean_article, clean_html)
  - pipeline:        orchestration helpers (run_api_collection_pipeline, run_url_collection_pipeline)
"""
