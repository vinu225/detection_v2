"""
module_2/tests/test_sentiment.py — Unit tests for sentiment_analyzer.py and scoring.py.
"""

import pytest
import numpy as np

from module_2_sentimental.sentiment_analyzer import SentimentAnalyzer
from module_2_sentimental.scoring import (
    calculate_sentiment_score,
    calculate_emotional_intensity,
    calculate_reliability,
    compute_all_scores
)

@pytest.fixture
def analyzer():
    return SentimentAnalyzer.get_instance()

def test_sentiment_positive(analyzer):
    # Trigger positive class in mock via word matches
    text = "The government successfully implemented a beneficial policy."
    label, confidence, probs, probs_dict = analyzer.analyze_text(text)
    
    assert label == "Positive"
    assert confidence > 0.8
    assert probs_dict["positive_probability"] > 0.8
    assert probs_dict["negative_probability"] < 0.1
    assert probs_dict["neutral_probability"] < 0.1

def test_sentiment_negative(analyzer):
    # Trigger negative class in mock
    text = "The economy suffered a devastating collapse."
    label, confidence, probs, probs_dict = analyzer.analyze_text(text)
    
    assert label == "Negative"
    assert confidence > 0.8
    assert probs_dict["negative_probability"] > 0.8

def test_sentiment_neutral(analyzer):
    # Trigger neutral class in mock
    text = "The meeting was held on Monday."
    label, confidence, probs, probs_dict = analyzer.analyze_text(text)
    
    assert label == "Neutral"
    assert confidence > 0.8
    assert probs_dict["neutral_probability"] > 0.8

def test_scoring_sentiment_score():
    assert calculate_sentiment_score("Positive", 0.95) == 95
    assert calculate_sentiment_score("Negative", 0.85) == -85
    assert calculate_sentiment_score("Neutral", 0.99) == 0

def test_scoring_emotional_intensity_advanced():
    # 1. Base intensity + intensifier boost ("very", "extremely") + emotional word ("devastating", "collapse")
    probs = {"negative_probability": 0.9, "neutral_probability": 0.05, "positive_probability": 0.05}
    text = "The economy suffered a very devastating collapse and it was extremely shocking."
    intensity = calculate_emotional_intensity("Negative", 0.9, probs, text)
    # Base: (abs(0.9-0.05)*0.5 + 0.9*0.5)*100 = 87.5
    # Word matches: devastating, collapse, shocking -> 3 * 6 = 18 boost
    # Intensifier matches: very, extremely -> 2 * 4 = 8 boost
    # Clipped at 100
    assert intensity == 100

    # 2. Neutral sentiment text should remain capped at 45.0
    probs_neu = {"negative_probability": 0.05, "neutral_probability": 0.9, "positive_probability": 0.05}
    text_neu = "The normal meeting was held today. It was very regular."
    intensity_neu = calculate_emotional_intensity("Neutral", 0.9, probs_neu, text_neu)
    assert intensity_neu <= 45

def test_scoring_reliability_advanced(analyzer):
    # 1. High agreement: chunks predict consistent outcomes
    chunk_probs_agree = np.array([
        [0.05, 0.10, 0.85],
        [0.06, 0.08, 0.86],
        [0.04, 0.12, 0.84]
    ])
    rel_agree = calculate_reliability(
        confidence=0.85,
        label="Positive",
        id2label=analyzer.id2label,
        standard_mapping=analyzer.standard_mapping,
        chunk_probabilities=chunk_probs_agree
    )
    assert rel_agree > 70

    # 2. Low agreement: chunks predict mixed positive and negative
    chunk_probs_mixed = np.array([
        [0.05, 0.10, 0.85],  # Positive
        [0.85, 0.10, 0.05],  # Negative
        [0.04, 0.12, 0.84]   # Positive
    ])
    rel_mixed = calculate_reliability(
        confidence=0.55,
        label="Positive",
        id2label=analyzer.id2label,
        standard_mapping=analyzer.standard_mapping,
        chunk_probabilities=chunk_probs_mixed
    )
    # Penalty from standard deviation + mixed label penalty (-15)
    assert rel_mixed < rel_agree - 20

def test_long_article_validation_5k(analyzer):
    # Create 5,000+ words article (Positive context)
    words = (["success"] * 2500) + (["beneficial"] * 2600)
    text = " ".join(words)
    
    label, confidence, probs, probs_dict = analyzer.analyze_text(text)
    
    # Assert chunk counts
    tokens = analyzer.tokenizer.encode(text, add_special_tokens=False)
    chunks = analyzer._chunk_tokens(tokens)
    assert len(chunks) > 10  # 5100 words should be at least 13 chunks (5100 / 350 stride)
    
    assert label == "Positive"
    assert confidence > 0.8

def test_long_article_validation_10k(analyzer):
    # Create 10,000+ words article (Negative context)
    words = (["collapse"] * 5000) + (["disaster"] * 5100)
    text = " ".join(words)
    
    label, confidence, probs, probs_dict = analyzer.analyze_text(text)
    
    tokens = analyzer.tokenizer.encode(text, add_special_tokens=False)
    chunks = analyzer._chunk_tokens(tokens)
    assert len(chunks) > 25
    
    assert label == "Negative"
    assert confidence > 0.8

def test_sliding_window_overlap(analyzer):
    # Validate the sliding window chunk boundaries and overlap
    # Let's say settings.chunk_size = 400 and overlap = 50. Stride is 350.
    # We pass a text that gets exactly 500 tokens
    tokens = list(range(500))
    chunks = analyzer._chunk_tokens(tokens)
    
    # Chunk 0: 0 to 400
    # Chunk 1: 350 to 500
    assert len(chunks) == 2
    assert len(chunks[0]) == 400
    assert len(chunks[1]) == 150
    # Overlap region check (tokens 350 to 400)
    assert chunks[0][350:] == chunks[1][:50]
