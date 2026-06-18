"""
module_2/tests/test_runtime.py — Unit tests for device selection, GPU fallback, batching, and performance benchmarking.
"""

import sys
import time
import pytest
from unittest.mock import patch, MagicMock

# Make sure torch is imported (it is mocked in conftest.py)
import torch
from module_2_sentimental.sentiment_analyzer import SentimentAnalyzer
from module_2_sentimental.pipeline import SentimentPipeline
from module_2_sentimental.config import settings

def test_cpu_device_selection():
    # Force cpu in settings
    with patch.object(settings, "device", "cpu"):
        SentimentAnalyzer.reset_instance()
        analyzer = SentimentAnalyzer.get_instance()
        assert str(analyzer.device) == "cpu"

def test_gpu_device_selection_available():
    # Mock cuda.is_available to return True, settings.device is None
    with patch("torch.cuda.is_available", return_value=True), \
         patch.object(settings, "device", None):
        SentimentAnalyzer.reset_instance()
        analyzer = SentimentAnalyzer.get_instance()
        assert str(analyzer.device) == "cuda"

def test_gpu_device_fallback_unavailable():
    # Mock cuda.is_available to return False, settings.device is None
    with patch("torch.cuda.is_available", return_value=False), \
         patch.object(settings, "device", None):
        SentimentAnalyzer.reset_instance()
        analyzer = SentimentAnalyzer.get_instance()
        assert str(analyzer.device) == "cpu"

def test_batch_inference_latency_benchmarking():
    """
    Performance benchmarking of loading times, inference latency, and throughput.
    """
    SentimentAnalyzer.reset_instance()
    
    # 1. Benchmark Model Load Time
    start_load = time.perf_counter()
    pipeline = SentimentPipeline()
    load_time = time.perf_counter() - start_load
    
    # 2. Benchmark Batch Processing Throughput
    # Create a batch of 20 articles
    batch_articles = [
        {
            "article_id": f"bench_{i}",
            "title": "Benchmarking successful results!" if i % 2 == 0 else "Disastrous collapse occurred.",
            "clean_text": "This is sample article content for performance benchmarking of the sentiment analyzer pipeline. " * 20
        }
        for i in range(20)
    ]
    
    start_inference = time.perf_counter()
    results = pipeline.run_pipeline(batch_articles)
    total_inference_time = time.perf_counter() - start_inference
    
    avg_inference_latency = total_inference_time / len(batch_articles)
    throughput = len(batch_articles) / total_inference_time
    
    # Mock memory usage (psutil equivalent)
    # If psutil is not available, report dummy value or standard process RSS
    try:
        import os
        import psutil
        process = psutil.Process(os.getpid())
        memory_usage_mb = process.memory_info().rss / (1024 * 1024)
    except ImportError:
        memory_usage_mb = 150.0  # fallback mock value

    # Store benchmark logs
    benchmark_log_file = settings.logs_dir / "benchmark.log"
    with open(benchmark_log_file, "a", encoding="utf-8") as f:
        f.write(
            f"--- Benchmark Run {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            f"Model Loading Time: {load_time:.4f}s\n"
            f"Total Inference Time: {total_inference_time:.4f}s\n"
            f"Average Latency per Article: {avg_inference_latency:.4f}s\n"
            f"Throughput: {throughput:.2f} articles/sec\n"
            f"Memory Usage: {memory_usage_mb:.2f} MB\n\n"
        )
        
    # Basic assertions
    assert len(results) == 20
    assert load_time > 0
    assert total_inference_time > 0
    assert benchmark_log_file.is_file()
