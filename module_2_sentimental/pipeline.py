"""
module_2/pipeline.py — Pipeline orchestration for the Sentiment Analysis module with suffix routing, metadata preservation, and ML feature compatibility.
"""

import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Union, Optional

from module_2_sentimental.config import settings
from module_2_sentimental.json_loader import load_json_file
from module_2_sentimental.html_loader import load_html_file
from module_2_sentimental.preprocessor import clean_text
from module_2_sentimental.sentiment_analyzer import SentimentAnalyzer
from module_2_sentimental.scoring import compute_all_scores

logger = logging.getLogger("sentiment_module")
logger.setLevel(logging.INFO)

if not logger.handlers:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d]: %(message)s")
    )
    logger.addHandler(file_handler)
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    logger.addHandler(stream_handler)


class SentimentPipeline:
    def __init__(self, model_name: Optional[str] = None):
        """
        Initializes the pipeline and retrieves the singleton SentimentAnalyzer.
        """
        logger.info("Initializing Sentiment Analysis Pipeline...")
        start_time = time.perf_counter()
        
        # Load the model via singleton pattern
        self.analyzer = SentimentAnalyzer.get_instance(model_name=model_name)
        
        elapsed = time.perf_counter() - start_time
        logger.info(f"Pipeline initialized in {elapsed:.2f}s.")

    def process_article_data(self, article: Dict[str, Any], strategy: str = "mean") -> Dict[str, Any]:
        """
        Processes a single article dictionary, preserving all rich metadata,
        performing separate headline/body analysis, and generating features.
        """
        # Preserving original metadata
        article_id = article.get("article_id") or article.get("id")
        if not article_id:
            # Generate deterministic fallback ID from title
            article_id = f"art_{hash(article.get('title', '')) & 0xffffffff:08x}"
            
        title = article.get("title", "").strip()
        body = article.get("clean_text") or article.get("content") or ""
        
        source = article.get("source") or ""
        author = article.get("author") or ""
        url = article.get("url") or ""
        pub_date = article.get("publication_date") or ""

        # Preprocessing text
        cleaned_title = clean_text(title)
        cleaned_body = clean_text(body)

        # Run independent body inference using chunking/sliding window
        body_tokens = self.analyzer.tokenizer.encode(cleaned_body, add_special_tokens=False)
        body_chunks = self.analyzer._chunk_tokens(body_tokens)
        
        # Performance check
        body_chunk_count = len(body_chunks)
        logger.debug(f"Article {article_id}: body has {len(body_tokens)} tokens, split into {body_chunk_count} chunks.")

        # Predict batch of chunks
        probs_array = self.analyzer._predict_batch(body_chunks)
        
        # Aggregate body predictions
        body_label, body_conf, body_agg_probs = self.analyzer._aggregate_predictions(probs_array, strategy=strategy)
        body_probs_dict = self.analyzer._map_probs_to_dict(body_agg_probs)
        
        # Predict headline
        hl_label, hl_conf, hl_probs, hl_probs_dict = self.analyzer.analyze_text(cleaned_title, strategy=strategy)
        
        headline_sentiment_res = {
            "label": hl_label,
            "confidence": round(hl_conf, 4),
            "negative_probability": hl_probs_dict["negative_probability"],
            "neutral_probability": hl_probs_dict["neutral_probability"],
            "positive_probability": hl_probs_dict["positive_probability"]
        }
        
        article_sentiment_res = {
            "label": body_label,
            "confidence": round(body_conf, 4),
            "negative_probability": body_probs_dict["negative_probability"],
            "neutral_probability": body_probs_dict["neutral_probability"],
            "positive_probability": body_probs_dict["positive_probability"]
        }
        
        # Calculate scoring metrics
        scores = compute_all_scores(
            headline_res={"label": hl_label, "confidence": hl_conf, "probabilities_dict": hl_probs_dict},
            article_res={"label": body_label, "confidence": body_conf, "probabilities_dict": body_probs_dict},
            article_text=cleaned_body,
            id2label=self.analyzer.id2label,
            standard_mapping=self.analyzer.standard_mapping,
            chunk_probs=probs_array
        )

        # Output with preserved metadata & timezone-aware UTC timestamps
        processed_timestamp = datetime.now(timezone.utc).isoformat()
        
        result = {
            "article_id": article_id,
            "source": source,
            "author": author,
            "url": url,
            "publication_date": pub_date,
            "processed_timestamp": processed_timestamp,
            
            # Separate Headline & Body Analyses
            "headline_sentiment": headline_sentiment_res,
            "article_sentiment": article_sentiment_res,
            
            # Flat features for downstream ML pipelines
            "negative_probability": body_probs_dict["negative_probability"],
            "neutral_probability": body_probs_dict["neutral_probability"],
            "positive_probability": body_probs_dict["positive_probability"],
            "sentiment_score": scores["sentiment_score"],
            "emotional_intensity": scores["emotional_intensity"],
            "sentiment_reliability": scores["sentiment_reliability"]
        }
        
        return result

    def load_and_route_file(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Suffix-based loading and routing. Returns a list of validated dictionaries.
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == ".json":
            return load_json_file(path)
        elif suffix in [".html", ".htm"]:
            data = load_html_file(path)
            # Assign deterministic fallback ID for HTML files
            if not data.get("article_id"):
                data["article_id"] = path.stem
            return [data]
        else:
            raise ValueError(f"Unsupported suffix '{suffix}' for file: {path}")

    def run_pipeline(
        self, 
        input_source: Union[str, Path, List[Dict[str, Any]]], 
        output_file: Optional[Union[str, Path]] = None,
        strategy: str = "mean"
    ) -> List[Dict[str, Any]]:
        """
        Executes the sentiment analysis pipeline.
        Saves the results to output_file.
        """
        logger.info("Starting pipeline execution run...")
        start_time = time.perf_counter()
        
        results = []
        skipped_files = 0
        failed_files = 0
        success_files = 0
        
        if isinstance(input_source, list):
            logger.info(f"Processing list of {len(input_source)} articles directly.")
            for idx, article in enumerate(input_source):
                try:
                    res = self.process_article_data(article, strategy=strategy)
                    results.append(res)
                except Exception as e:
                    logger.error(f"Failed to process list item at index {idx}: {e}")
        else:
            path = Path(input_source)
            if path.is_file():
                try:
                    articles = self.load_and_route_file(path)
                    for article in articles:
                        res = self.process_article_data(article, strategy=strategy)
                        results.append(res)
                    success_files += 1
                except Exception as e:
                    logger.error(f"Pipeline execution failed for file {path}: {e}")
                    failed_files += 1
            elif path.is_dir():
                # Scan for *.json, *.html, *.htm
                files = []
                for extension in ["*.json", "*.html", "*.htm"]:
                    files.extend(path.glob(extension))
                
                logger.info(f"Directory batching found {len(files)} files to process in {path}.")
                
                for f in files:
                    try:
                        articles = self.load_and_route_file(f)
                        for article in articles:
                            res = self.process_article_data(article, strategy=strategy)
                            results.append(res)
                        success_files += 1
                    except Exception as e:
                        logger.error(f"Pipeline execution failed for batch item {f}: {e}")
                        failed_files += 1
            else:
                logger.error(f"Input path does not exist: {input_source}")
                raise FileNotFoundError(f"Input source path does not exist: {input_source}")

        # Persist results
        out_path = Path(output_file or settings.results_file)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Saved {len(results)} sentiment features to {out_path}")
        except Exception as e:
            logger.error(f"Failed to write results to {out_path}: {e}")

        total_time = time.perf_counter() - start_time
        logger.info(
            f"Pipeline batch run completed in {total_time:.2f}s. "
            f"Total Processed: {len(results)}, Success Files: {success_files}, Failed Files: {failed_files}"
        )
        return results
