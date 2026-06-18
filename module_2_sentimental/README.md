# Module 2 (Sentimental) — RoBERTa Sentiment Analysis

This module is responsible for analyzing the sentiment polarity, emotional intensity, and inference reliability of preprocessed news articles. It loads articles in HTML or JSON formats and performs batch inference using a fine-tuned RoBERTa transformer model.

---

## Technical Architecture

```
Processed Article (HTML/JSON)
            ↓
     Loader (html_loader / json_loader)
            ↓
     Tokenizer & Sliding Window (sentiment_analyzer)
            ↓
     RoBERTa Inference Model
            ↓
     Scoring Engine (scoring)
            ↓
     Results JSON / DB Update
```

---

## Component Details

- **`config.py`**: Configuration parameters for model weights path, batch size, threshold values, and chunking parameters.
- **`json_loader.py` / `html_loader.py`**: Substantive parser utilities to ingest processed files into common model data types.
- **`preprocessor.py`**: Model-specific text normalizer and cleaner.
- **`sentiment_analyzer.py`**: Model load helper, sliding window text segmenter, and GPU-accelerated inference wrapper.
- **`scoring.py`**: Sentiment index calculators (positive, neutral, negative consensus), emotional variance indicator, and data reliability metrics.
- **`pipeline.py`**: Orchestrates loading, preprocessing, batch prediction, scoring, and output generation.

---

## Execution & Verification

Run the test suite:
```bash
pytest module_2_sentimental/tests/ -v
```
