"""
module_2/scoring.py — Computation of advanced sentiment, emotional intensity, and reliability scores.
"""

import re
import logging
import numpy as np
from typing import Dict, Any, List, Optional

logger = logging.getLogger("sentiment_module.scoring")

# List of emotionally charged words to boost intensity
EMOTIONAL_WORDS = {
    "devastating", "collapse", "disaster", "crisis", "tragedy", "horrible", "terrible", "worst", "ruin", "fail",
    "successful", "triumph", "excellent", "outstanding", "beneficial", "thrilled", "greatest", "best", "perfect",
    "furious", "outrage", "shocking", "scandal", "catastrophe", "brilliant", "delighted", "severe", "dreadful",
    "incredible", "catastrophic", "unbelievable", "amazing", "horrific"
}

# List of intensifiers to boost intensity
INTENSIFIERS = {
    "very", "extremely", "really", "highly", "strongly", "completely", "absolutely", "incredibly", "remarkably",
    "totally", "dramatically", "severely", "wildly"
}

def calculate_sentiment_score(label: str, confidence: float) -> int:
    """
    Computes a basic sentiment score from -100 to +100.
    """
    if label == "Positive":
        score = 100 * confidence
    elif label == "Negative":
        score = -100 * confidence
    else:  # Neutral
        score = 0.0
    return int(round(score))

def calculate_emotional_intensity(
    label: str, 
    confidence: float, 
    probs_dict: Dict[str, float], 
    text: str
) -> int:
    """
    Computes emotional intensity on a scale of 0 to 100.
    Combines:
      - Polarity strength: abs(positive_probability - negative_probability)
      - Confidence
      - Frequency of emotional words
      - Frequency of intensifiers
      - Exclamation marks
    """
    pos_prob = probs_dict.get("positive_probability", 0.0)
    neg_prob = probs_dict.get("negative_probability", 0.0)
    
    # 1. Polarity strength
    polarity_strength = abs(pos_prob - neg_prob)
    
    # 2. Base intensity (combination of polarity and confidence)
    # Scaled to 0-100
    base_intensity = (polarity_strength * 0.5 + confidence * 0.5) * 100.0
    
    # If the label is Neutral, reduce base intensity significantly
    if label == "Neutral":
        base_intensity *= 0.3

    # 3. Scan text for intensifiers and emotional words
    boost = 0.0
    words = re.findall(r"\b\w+\b", text.lower())
    
    # Frequency of emotional words
    emotional_matches = [w for w in words if w in EMOTIONAL_WORDS]
    boost += min(len(emotional_matches) * 6.0, 24.0)  # Max +24 boost
    
    # Frequency of intensifiers
    intensifier_matches = [w for w in words if w in INTENSIFIERS]
    boost += min(len(intensifier_matches) * 4.0, 16.0)  # Max +16 boost
    
    # Exclamation mark boost: +5 per exclamation mark up to +15
    exclamations = len(re.findall(r"!", text))
    boost += min(exclamations * 5.0, 15.0)

    # Combine
    final_intensity = base_intensity + boost
    
    # Neutral cap
    if label == "Neutral":
        final_intensity = min(final_intensity, 45.0)
        
    return int(round(clip_score(final_intensity, 0.0, 100.0)))

def calculate_reliability(
    confidence: float,
    label: str,
    id2label: Dict[int, str],
    standard_mapping: Dict[int, str],
    chunk_probabilities: Optional[np.ndarray] = None
) -> int:
    """
    Computes sentiment reliability on a scale of 0 to 100.
    Factors:
      - Stable confidence
      - Consistent chunk predictions
      - Low sentiment variance
    """
    base_reliability = confidence * 100.0
    
    if chunk_probabilities is None or len(chunk_probabilities) <= 1:
        # Single chunk: reliability is derived directly from confidence
        return int(round(clip_score(base_reliability, 0.0, 100.0)))

    # Get final predicted class standard index
    # We find which index corresponds to our final label
    final_pred_class_idx = -1
    for idx, name in standard_mapping.items():
        if name == label:
            final_pred_class_idx = idx
            break

    # Determine predicted class for each chunk
    chunk_preds = np.argmax(chunk_probabilities, axis=1)
    
    # 1. Agreement ratio: fraction of chunks that agree with final label
    if final_pred_class_idx != -1:
        agreement_ratio = np.mean(chunk_preds == final_pred_class_idx)
    else:
        agreement_ratio = 1.0
        
    # 2. Sentiment variance across chunks
    # std deviation per class across chunks
    std_per_class = np.std(chunk_probabilities, axis=0)
    mean_std = float(np.mean(std_per_class))
    
    # 3. Confidence instability
    # std deviation of chunk confidences
    chunk_confidences = np.max(chunk_probabilities, axis=1)
    conf_std = float(np.std(chunk_confidences))

    # Calculate scores
    consensus_score = agreement_ratio * 100.0
    
    # Penalize variance: std dev of 0.25 is moderate variation, 0.4+ is huge
    variance_penalty = mean_std * 80.0  # Up to 40 penalty
    
    # Penalize instability of confidence
    instability_penalty = conf_std * 50.0  # Up to 25 penalty

    # Reliability calculation: weighted consensus and base, minus penalties
    final_reliability = (0.5 * base_reliability) + (0.5 * consensus_score) - variance_penalty - instability_penalty
    
    # Decrease reliability if we have mixed sentiment chunks (both Positive and Negative predictions present)
    # Map predictions to standard labels
    predicted_standard_labels = [standard_mapping.get(int(idx), "Neutral") for idx in chunk_preds]
    if "Positive" in predicted_standard_labels and "Negative" in predicted_standard_labels:
        # Mixed sentiment penalty: subtract additional 15 points
        final_reliability -= 15.0

    return int(round(clip_score(final_reliability, 0.0, 100.0)))

def clip_score(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

def compute_all_scores(
    headline_res: Dict[str, Any],
    article_res: Dict[str, Any],
    article_text: str,
    id2label: Dict[int, str],
    standard_mapping: Dict[int, str],
    chunk_probs: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Combines headline and article predictions, raw distributions, and chunk probabilities
    to compute advanced sentiment scores.
    """
    art_label = article_res["label"]
    art_conf = article_res["confidence"]
    art_probs_dict = article_res["probabilities_dict"]
    
    hl_label = headline_res["label"]
    hl_conf = headline_res["confidence"]
    hl_probs_dict = headline_res["probabilities_dict"]

    # 1. Sentiment Score: 80% weight on body, 20% weight on headline
    art_score = calculate_sentiment_score(art_label, art_conf)
    hl_score = calculate_sentiment_score(hl_label, hl_conf)
    sentiment_score = int(round((0.8 * art_score) + (0.2 * hl_score)))
    
    # 2. Emotional Intensity (calculated on body text)
    emotional_intensity = calculate_emotional_intensity(
        label=art_label, 
        confidence=art_conf, 
        probs_dict=art_probs_dict, 
        text=article_text
    )
    
    # 3. Sentiment Reliability (calculated on body text chunks)
    sentiment_reliability = calculate_reliability(
        confidence=art_conf,
        label=art_label,
        id2label=id2label,
        standard_mapping=standard_mapping,
        chunk_probabilities=chunk_probs
    )
    
    return {
        "sentiment_score": sentiment_score,
        "emotional_intensity": emotional_intensity,
        "sentiment_reliability": sentiment_reliability
    }
