"""
module_2/tests/test_json_loader.py — Unit tests for json_loader.py.
"""

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from module_2_sentimental.json_loader import load_json_file, validate_article

def test_validate_article_valid():
    data = {
        "article_id": "123",
        "title": "Valid Article Title",
        "clean_text": "This is the clean text of the article.",
        "source": "BBC",
        "author": "Reporter",
        "publication_date": "2026-06-16",
        "url": "https://bbc.com/news/123"
    }
    validated = validate_article(data)
    assert validated["article_id"] == "123"
    assert validated["title"] == "Valid Article Title"
    assert validated["clean_text"] == "This is the clean text of the article."
    assert validated["source"] == "BBC"

def test_validate_article_missing_required():
    data = {
        "article_id": "123",
        "title": "Missing clean_text"
    }
    with pytest.raises(Exception):
        validate_article(data)

def test_load_json_file_single():
    article = {
        "article_id": "456",
        "title": "Single Article",
        "clean_text": "Content of single article."
    }
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(article, f)
        temp_path = f.name
        
    try:
        articles = load_json_file(temp_path)
        assert len(articles) == 1
        assert articles[0]["article_id"] == "456"
        assert articles[0]["title"] == "Single Article"
    finally:
        Path(temp_path).unlink()

def test_load_json_file_array():
    articles = [
        {"article_id": "a1", "title": "Title 1", "clean_text": "Text 1"},
        {"article_id": "a2", "title": "Title 2", "clean_text": "Text 2"},
        {"article_id": "a3", "title": "Title 3", "clean_text": "Text 3"}
    ]
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(articles, f)
        temp_path = f.name
        
    try:
        loaded = load_json_file(temp_path)
        assert len(loaded) == 3
        assert loaded[0]["article_id"] == "a1"
        assert loaded[2]["clean_text"] == "Text 3"
    finally:
        Path(temp_path).unlink()

def test_load_json_file_array_with_one_invalid():
    articles = [
        {"article_id": "a1", "title": "Title 1", "clean_text": "Text 1"},
        {"article_id": "a2", "title": "Invalid Article"}  # missing clean_text
    ]
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(articles, f)
        temp_path = f.name
        
    try:
        # Should skip index 1 and return list with 1 valid article
        loaded = load_json_file(temp_path)
        assert len(loaded) == 1
        assert loaded[0]["article_id"] == "a1"
    finally:
        Path(temp_path).unlink()

def test_load_json_file_all_invalid():
    articles = [
        {"article_id": "a1", "title": "Title 1"},  # missing clean_text
        {"article_id": "a2", "title": "Title 2"}   # missing clean_text
    ]
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(articles, f)
        temp_path = f.name
        
    try:
        with pytest.raises(ValueError, match="All articles in the list failed schema validation"):
            load_json_file(temp_path)
    finally:
        Path(temp_path).unlink()

def test_load_json_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_json_file("non_existent_file_12345.json")

def test_load_json_file_empty():
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        temp_path = f.name
        
    try:
        loaded = load_json_file(temp_path)
        assert loaded == []
    finally:
        Path(temp_path).unlink()

def test_load_json_file_malformed():
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write("{invalid_json: true")
        temp_path = f.name
        
    try:
        with pytest.raises(ValueError, match="Malformed JSON"):
            load_json_file(temp_path)
    finally:
        Path(temp_path).unlink()

def test_load_json_file_invalid_type():
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write('"simple string"')
        temp_path = f.name
        
    try:
        with pytest.raises(ValueError, match="JSON top-level must be dict or list"):
            load_json_file(temp_path)
    finally:
        Path(temp_path).unlink()

def test_load_json_file_metadata_preservation():
    article = {
        "article_id": "meta_1",
        "title": "Preserved Title",
        "clean_text": "Body content here.",
        "source": "New York Times",
        "author": "Jane Smith",
        "url": "https://nytimes.com/preserved",
        "publication_date": "2026-06-16T15:00:00Z"
    }
    
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(article, f)
        temp_path = f.name
        
    try:
        loaded = load_json_file(temp_path)
        assert len(loaded) == 1
        assert loaded[0]["source"] == "New York Times"
        assert loaded[0]["author"] == "Jane Smith"
        assert loaded[0]["url"] == "https://nytimes.com/preserved"
        assert loaded[0]["publication_date"] == "2026-06-16T15:00:00Z"
    finally:
        Path(temp_path).unlink()
