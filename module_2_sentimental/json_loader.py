"""
module_2/json_loader.py — Data loading, validation, and metadata preservation of JSON news articles.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from pydantic import BaseModel, Field, ValidationError, model_validator, ConfigDict

logger = logging.getLogger("sentiment_module.json_loader")

class ArticleSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

    article_id: Optional[str] = Field(default=None, description="Unique article ID")
    title: str = Field(..., min_length=1, description="Article title/headline")
    clean_text: Optional[str] = Field(default=None, description="Cleaned body text of the article")
    content: Optional[str] = Field(default=None, description="Alternative field for body text")
    
    # Metadata fields to preserve
    source: Optional[str] = Field(default="", description="Publisher or feed source")
    author: Optional[str] = Field(default="", description="Author of the article")
    url: Optional[str] = Field(default="", description="Original article URL")
    publication_date: Optional[str] = Field(default="", description="ISO publication date")

    @model_validator(mode="after")
    def check_text_exists(self) -> "ArticleSchema":
        text = self.clean_text or self.content
        if not text or not text.strip():
            raise ValueError("At least one of 'clean_text' or 'content' must be a non-empty string.")
        
        # Populate clean_text from content if missing
        if not self.clean_text:
            self.clean_text = self.content
        return self


def validate_article(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a single article dictionary against ArticleSchema.
    Returns the validated dictionary with preserved metadata.
    """
    article = ArticleSchema(**data)
    return article.model_dump()


def load_json_file(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Loads and validates articles from a JSON file.
    Supports:
      - Single article object {}
      - Array of article objects [{}]
    Returns:
      List of validated article dicts.
    Raises:
      FileNotFoundError: If file does not exist.
      ValueError: For malformed JSON or invalid schema.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.error(f"JSON file not found: {path}")
        raise FileNotFoundError(f"JSON file not found: {path}")

    if path.stat().st_size == 0:
        logger.warning(f"JSON file is empty: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in file {path}: {e}")
        raise ValueError(f"Malformed JSON: {e}")

    validated_articles = []
    
    if isinstance(data, dict):
        try:
            validated = validate_article(data)
            validated_articles.append(validated)
        except ValidationError as e:
            logger.error(f"Schema validation error in {path}: {e}")
            raise ValueError(f"Schema validation error: {e}")
            
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                logger.warning(f"Item at index {idx} in {path} is not an object. Skipping.")
                continue
            try:
                validated = validate_article(item)
                validated_articles.append(validated)
            except ValidationError as e:
                logger.warning(f"Skipping invalid article at index {idx} in {path}: {e}")
                
        if not validated_articles and data:
            raise ValueError("All articles in the list failed schema validation.")
    else:
        logger.error(f"Unsupported JSON format: {type(data)}")
        raise ValueError(f"JSON top-level must be dict or list, got {type(data).__name__}")

    logger.info(f"Successfully loaded and validated {len(validated_articles)} articles from {path}")
    return validated_articles
