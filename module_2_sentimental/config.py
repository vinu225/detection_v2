"""
module_2/config.py — Configuration settings for the RoBERTa Sentiment Analysis module.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for module_2
BASE_DIR = Path(__file__).resolve().parent

class SentimentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTIMENT_",
        case_sensitive=False
    )
    # Model configuration
    primary_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    alternative_model: str = "siebert/sentiment-roberta-large-english"
    model_name: str = Field(default="cardiffnlp/twitter-roberta-base-sentiment-latest")
    
    # Execution options
    device: Optional[str] = None  # Auto-detected if None (GPU/CPU)
    batch_size: int = 4
    
    # Token chunking parameters for long articles
    chunk_size: int = 400
    chunk_overlap: int = 50
    
    # Paths (relative to module_2 base directory)
    data_raw_dir: Path = BASE_DIR / "data" / "raw"
    data_processed_dir: Path = BASE_DIR / "data" / "processed"
    data_test_dir: Path = BASE_DIR / "data" / "test_data"
    logs_dir: Path = BASE_DIR / "logs"
    results_file: Path = BASE_DIR / "results" / "sentiment_results.json"
    log_file: Path = BASE_DIR / "logs" / "sentiment.log"

# Singleton instance of config
settings = SentimentConfig()

# Ensure directories exist
settings.data_raw_dir.mkdir(parents=True, exist_ok=True)
settings.data_processed_dir.mkdir(parents=True, exist_ok=True)
settings.data_test_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)
settings.results_file.parent.mkdir(parents=True, exist_ok=True)
