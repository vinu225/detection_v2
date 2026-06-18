"""
module_2 — RoBERTa Sentiment Analysis module.

Exposes:
  - config:             Sentiment-specific settings (model, device, batch, paths)
  - json_loader:        Load and validate JSON news articles
  - html_loader:        Extract text from HTML news files
  - preprocessor:       Text normalization for RoBERTa input
  - sentiment_analyzer: Core RoBERTa inference engine (singleton)
  - scoring:            Advanced scoring metrics
  - pipeline:           Orchestration — run_pipeline()
"""
