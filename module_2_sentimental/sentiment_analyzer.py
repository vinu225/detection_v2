"""
module_2/sentiment_analyzer.py — RoBERTa Sentiment Analysis engine with singleton caching and raw probability vector outputs.
"""

import logging
import torch
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F

from module_2_sentimental.config import settings

logger = logging.getLogger("sentiment_module.sentiment_analyzer")

class SentimentAnalyzer:
    _instance: Optional["SentimentAnalyzer"] = None

    @classmethod
    def get_instance(cls, model_name: Optional[str] = None) -> "SentimentAnalyzer":
        """
        Singleton retrieval method. Ensures the model is loaded once and shared.
        """
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Resets the singleton instance (useful for test isolation).
        """
        cls._instance = None

    def __init__(self, model_name: Optional[str] = None):
        """
        Loads the RoBERTa model and tokenizer.
        """
        self.model_name = model_name or settings.model_name
        
        # Detect device
        if settings.device:
            self.device = torch.device(settings.device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            
        logger.info(f"Initializing SentimentAnalyzer (Singleton) with model: {self.model_name} on device: {self.device}")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            # Map label IDs to standardized names
            self.id2label = self.model.config.id2label
            self._build_label_mapping()
            logger.info("Model loaded and initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to load RoBERTa model {self.model_name}: {e}")
            raise RuntimeError(f"Model initialization error: {e}")

    def _build_label_mapping(self):
        """
        Creates a map from index to standard labels: 'Negative', 'Neutral', 'Positive'.
        """
        self.standard_mapping = {}
        for idx, label in self.id2label.items():
            label_lower = label.lower()
            if "neg" in label_lower:
                self.standard_mapping[idx] = "Negative"
            elif "pos" in label_lower:
                self.standard_mapping[idx] = "Positive"
            else:
                self.standard_mapping[idx] = "Neutral"

        self.has_neutral = "Neutral" in self.standard_mapping.values()
        logger.debug(f"Label mapping built: {self.standard_mapping} (has_neutral={self.has_neutral})")

    def _chunk_tokens(self, token_ids: List[int]) -> List[List[int]]:
        """
        Splits token IDs list into overlapping chunks based on settings.
        """
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap
        stride = chunk_size - overlap
        
        if stride <= 0:
            logger.warning("Overlap >= Chunk size. Disabling overlap.")
            stride = chunk_size
            
        chunks = []
        n = len(token_ids)
        
        if n == 0:
            return [[self.tokenizer.cls_token_id, self.tokenizer.sep_token_id]]
            
        start = 0
        while start < n:
            end = min(start + chunk_size, n)
            chunk = token_ids[start:end]
            chunks.append(chunk)
            if end == n:
                break
            start += stride
            
        return chunks

    def _predict_batch(self, input_ids_list: List[List[int]]) -> np.ndarray:
        """
        Performs batch inference on a list of token ID sequences.
        Returns a numpy array of probabilities with shape (batch_size, num_classes).
        """
        cls_id = self.tokenizer.cls_token_id
        sep_id = self.tokenizer.sep_token_id
        
        processed_inputs = []
        for seq in input_ids_list:
            processed_inputs.append([cls_id] + seq + [sep_id])
            
        max_len = max(len(s) for s in processed_inputs)
        
        padded_inputs = []
        attention_masks = []
        
        for seq in processed_inputs:
            pad_len = max_len - len(seq)
            padded_inputs.append(seq + [self.tokenizer.pad_token_id] * pad_len)
            attention_masks.append([1] * len(seq) + [0] * pad_len)
            
        inputs_t = torch.tensor(padded_inputs, dtype=torch.long, device=self.device)
        masks_t = torch.tensor(attention_masks, dtype=torch.long, device=self.device)
        
        with torch.no_grad():
            outputs = self.model(input_ids=inputs_t, attention_mask=masks_t)
            logits = outputs.logits
            probs = F.softmax(logits, dim=-1)
            
        return probs.cpu().numpy()

    def _map_probs_to_dict(self, probs: np.ndarray) -> Dict[str, float]:
        """
        Maps standard class indices to negative/neutral/positive probability keys.
        """
        probs_dict = {
            "negative_probability": 0.0,
            "neutral_probability": 0.0,
            "positive_probability": 0.0
        }
        for idx, val in enumerate(probs):
            label = self.standard_mapping.get(idx)
            if label == "Negative":
                probs_dict["negative_probability"] = round(float(val), 4)
            elif label == "Positive":
                probs_dict["positive_probability"] = round(float(val), 4)
            elif label == "Neutral":
                probs_dict["neutral_probability"] = round(float(val), 4)
        return probs_dict

    def _aggregate_predictions(self, probs: np.ndarray, strategy: str = "mean") -> Tuple[str, float, np.ndarray]:
        """
        Aggregates multiple chunk prediction probabilities.
        """
        if strategy == "weighted":
            confidences = np.max(probs, axis=1)
            total_conf = np.sum(confidences)
            if total_conf > 0:
                weights = confidences / total_conf
                agg_probs = np.average(probs, axis=0, weights=weights)
            else:
                agg_probs = np.mean(probs, axis=0)
        else:
            agg_probs = np.mean(probs, axis=0)
            
        pred_idx = int(np.argmax(agg_probs))
        label = self.standard_mapping[pred_idx]
        confidence = float(agg_probs[pred_idx])
        
        return label, confidence, agg_probs

    def analyze_text(self, text: str, strategy: str = "mean") -> Tuple[str, float, np.ndarray, Dict[str, float]]:
        """
        Runs sentiment analysis on a piece of text. Handles long texts via chunking.
        Returns:
            Tuple containing:
              - label: 'Negative', 'Neutral', or 'Positive'
              - confidence: float score
              - raw_probabilities: full probability distribution as numpy array
              - probability_dict: mapped keys {negative_probability, neutral_probability, positive_probability}
        """
        if not text.strip():
            num_classes = len(self.id2label)
            default_probs = np.zeros(num_classes)
            neutral_idx = next((k for k, v in self.standard_mapping.items() if v == "Neutral"), 0)
            default_probs[neutral_idx] = 1.0
            prob_dict = self._map_probs_to_dict(default_probs)
            return self.standard_mapping[neutral_idx], 1.0, default_probs, prob_dict
            
        # Tokenize
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        
        # Split into chunks
        chunks = self._chunk_tokens(tokens)
        
        # Batch inference
        batch_size = settings.batch_size
        all_probs = []
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            probs_batch = self._predict_batch(batch_chunks)
            all_probs.append(probs_batch)
            
        probs_array = np.vstack(all_probs)
        
        # Aggregate
        label, confidence, agg_probs = self._aggregate_predictions(probs_array, strategy=strategy)
        prob_dict = self._map_probs_to_dict(agg_probs)
        return label, confidence, agg_probs, prob_dict
