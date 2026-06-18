"""
module_2/tests/test_pipeline.py — Integration and orchestration tests for pipeline.py.
"""

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from datetime import datetime, timezone

from module_2_sentimental.pipeline import SentimentPipeline
from module_2_sentimental.config import settings

@pytest.fixture
def pipeline():
    return SentimentPipeline()

def test_pipeline_process_article_data(pipeline):
    article = {
        "article_id": "test_id_123",
        "title": "A highly successful project launch!",
        "clean_text": "This project succeeded in all its major milestones and achieved excellent reviews.",
        "source": "TechNews",
        "author": "Alice Smith",
        "url": "https://technews.com/launch",
        "publication_date": "2026-06-16T12:00:00Z"
    }
    
    res = pipeline.process_article_data(article)
    
    # 1. Verify rich metadata preservation
    assert res["article_id"] == "test_id_123"
    assert res["source"] == "TechNews"
    assert res["author"] == "Alice Smith"
    assert res["url"] == "https://technews.com/launch"
    assert res["publication_date"] == "2026-06-16T12:00:00Z"
    
    # 2. Verify timezone-aware UTC processed timestamp
    processed_time = datetime.fromisoformat(res["processed_timestamp"])
    assert processed_time.tzinfo is not None
    assert processed_time.tzinfo == timezone.utc

    # 3. Verify separate headline vs body sentiment outputs
    assert "headline_sentiment" in res
    assert "article_sentiment" in res
    assert res["headline_sentiment"]["label"] == "Positive"
    assert res["article_sentiment"]["label"] == "Positive"
    
    # 4. Verify raw prediction distribution vectors
    assert "negative_probability" in res
    assert "neutral_probability" in res
    assert "positive_probability" in res
    assert res["positive_probability"] > 0.8
    assert res["headline_sentiment"]["positive_probability"] > 0.8
    
    # 5. Verify flat compatibility scores
    assert res["sentiment_score"] > 0
    assert 0 <= res["emotional_intensity"] <= 100
    assert 0 <= res["sentiment_reliability"] <= 100

def test_pipeline_run_single_json_file(pipeline):
    article = {
        "article_id": "json_test",
        "title": "Economy suffered catastrophic failure",
        "clean_text": "The latest figures show a complete collapse of all production lines. Investors suffer.",
        "source": "FinanceDaily"
    }
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(article, f)
        temp_path = f.name
        
    try:
        results = pipeline.run_pipeline(temp_path)
        assert len(results) == 1
        assert results[0]["article_id"] == "json_test"
        assert results[0]["article_sentiment"]["label"] == "Negative"
        assert results[0]["source"] == "FinanceDaily"
        assert results[0]["sentiment_score"] < 0
        
        # Check output file is created
        assert settings.results_file.is_file()
        with open(settings.results_file, "r", encoding="utf-8") as rf:
            output_data = json.load(rf)
            assert len(output_data) == 1
            assert output_data[0]["article_id"] == "json_test"
            assert output_data[0]["negative_probability"] > 0.8
    finally:
        Path(temp_path).unlink()
        if settings.results_file.is_file():
            settings.results_file.unlink()

def test_pipeline_run_single_html_file(pipeline):
    # Contains HTML tags and meta tags for metadata preservation
    html = """
    <html>
      <head>
        <title>Success Title</title>
        <meta name="author" content="Bob Johnson">
        <meta property="article:published_time" content="2026-06-16T14:30:00Z">
        <meta property="og:site_name" content="HTML Daily">
      </head>
      <body>
        <h1>A very successful and beneficial breakthrough</h1>
        <p>Our team achieved perfect results in the lab, succeeding beyond expectations.</p>
      </body>
    </html>
    """
    
    with NamedTemporaryFile(mode="w+", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        temp_path = f.name
        
    try:
        results = pipeline.run_pipeline(temp_path)
        assert len(results) == 1
        assert results[0]["article_id"] == Path(temp_path).stem
        assert results[0]["author"] == "Bob Johnson"
        assert results[0]["publication_date"] == "2026-06-16T14:30:00Z"
        assert results[0]["source"] == "HTML Daily"
        assert results[0]["headline_sentiment"]["label"] == "Positive"
        assert results[0]["article_sentiment"]["label"] == "Positive"
    finally:
        Path(temp_path).unlink()
        if settings.results_file.is_file():
            settings.results_file.unlink()

def test_pipeline_run_directory_mixed(pipeline):
    # 1. JSON single article dict
    json_article = {"article_id": "d1", "title": "Great success!", "clean_text": "Highly beneficial."}
    
    # 2. JSON array articles list
    json_array = [
        {"article_id": "d2", "title": "Devastating crisis", "clean_text": "Complete collapse."},
        {"article_id": "d3", "title": "Normal meeting", "clean_text": "The meeting was held Monday."}
    ]
    
    with TemporaryDirectory() as temp_dir:
        # Write json file 1
        json_path_1 = Path(temp_dir) / "article1.json"
        with open(json_path_1, "w", encoding="utf-8") as f:
            json.dump(json_article, f)
            
        # Write json file 2 (array)
        json_path_2 = Path(temp_dir) / "articles_array.json"
        with open(json_path_2, "w", encoding="utf-8") as f:
            json.dump(json_array, f)
            
        # Write html file
        html_path = Path(temp_dir) / "page.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><head><title>Success Headline</title></head><body><h1>Beautiful breakthrough</h1><p>Perfect success.</p></body></html>")
            
        # Run pipeline on directory (mixed suffix routing)
        results = pipeline.run_pipeline(temp_dir)
        
        # 1 from JSON 1 + 2 from JSON Array + 1 from HTML = 4 total
        assert len(results) == 4
        
        ids = {r["article_id"] for r in results}
        assert "d1" in ids
        assert "d2" in ids
        assert "d3" in ids
        assert "page" in ids

def test_pipeline_run_list_input(pipeline):
    articles = [
        {"article_id": "l1", "title": "Beautiful day!", "clean_text": "Everything is perfect."},
        {"article_id": "l2", "title": "Heavy rains", "clean_text": "No major details."}
    ]
    
    results = pipeline.run_pipeline(articles)
    assert len(results) == 2
    assert results[0]["article_id"] == "l1"
    assert results[0]["article_sentiment"]["label"] == "Positive"

def test_pipeline_invalid_path(pipeline):
    with pytest.raises(FileNotFoundError):
        pipeline.run_pipeline("non_existent_path_12345")
        
def test_pipeline_unsupported_suffix(pipeline):
    with NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        f.write("unsupported text content")
        temp_path = f.name
    try:
        results = pipeline.run_pipeline(temp_path)
        assert len(results) == 0
    finally:
        Path(temp_path).unlink()
