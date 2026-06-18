"""
module_2/tests/conftest.py — Pytest configuration and full module mocks for torch and transformers.
This allows running tests offline without torch or transformers installed.
"""

import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# --- Define Mock Tensor and Torch functional behavior ---
class MockTensor:
    def __init__(self, data):
        self.data = np.array(data)
        self.shape = self.data.shape

    def tolist(self):
        return self.data.tolist()

    def cpu(self):
        return self

    def numpy(self):
        return self.data

class NoGradContext:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# --- Create Mock Modules ---
mock_torch = MagicMock()
mock_torch.long = 1
mock_torch.float = 2
mock_torch.device.side_effect = lambda dev: dev
mock_torch.tensor.side_effect = lambda data, **kwargs: MockTensor(data)
mock_torch.no_grad.side_effect = lambda: NoGradContext()

mock_f = MagicMock()
def mock_softmax(tensor, dim=-1):
    logits = tensor.data
    # Subtract max for numerical stability
    exp_logits = np.exp(logits - np.max(logits, axis=dim, keepdims=True))
    probs = exp_logits / np.sum(exp_logits, axis=dim, keepdims=True)
    return MockTensor(probs)
mock_f.softmax.side_effect = mock_softmax

# --- Insert Mock Modules into sys.modules ---
mock_nn = MagicMock()
mock_nn.functional = mock_f
mock_torch.nn = mock_nn

sys.modules['torch'] = mock_torch
sys.modules['torch.nn'] = mock_nn
sys.modules['torch.nn.functional'] = mock_f

# Mock transformers
mock_transformers = MagicMock()
sys.modules['transformers'] = mock_transformers

# --- Define Mock Tokenizer and Model for Pretrained Loading ---
class MockTokenizer:
    def __init__(self):
        self.cls_token_id = 0
        self.pad_token_id = 1
        self.sep_token_id = 2
        
    def encode(self, text, add_special_tokens=False):
        text_lower = text.lower()
        tokens = []
        words = text_lower.split()
        for word in words:
            if any(p in word for p in ["success", "beneficial", "perfect", "excellent"]):
                tokens.append(100)
            elif any(n in word for n in ["devastate", "collapse", "suffer", "disaster"]):
                tokens.append(200)
            elif any(neu in word for neu in ["monday", "meeting", "held"]):
                tokens.append(300)
            else:
                tokens.append(500)
        if not tokens:
            tokens = [500]
        return tokens

class MockConfig:
    def __init__(self):
        self.id2label = {
            0: "negative",
            1: "neutral",
            2: "positive"
        }

class MockModelOutputs:
    def __init__(self, logits):
        self.logits = logits

class MockModel:
    def __init__(self):
        self.config = MockConfig()
        
    def to(self, device):
        return self
        
    def eval(self):
        return self
        
    def __call__(self, input_ids, attention_mask=None, **kwargs):
        # input_ids is a MockTensor
        batch_size = input_ids.shape[0]
        logits_list = []
        
        for i in range(batch_size):
            row = input_ids.tolist()[i]
            if 100 in row:
                logits_list.append([-2.0, -1.0, 5.0])
            elif 200 in row:
                logits_list.append([5.0, -1.0, -2.0])
            elif 300 in row:
                logits_list.append([-2.0, 5.0, -2.0])
            else:
                logits_list.append([-1.0, 3.0, -1.0])
                
        return MockModelOutputs(MockTensor(logits_list))

from module_2_sentimental.sentiment_analyzer import SentimentAnalyzer

@pytest.fixture(autouse=True)
def setup_transformers_mocks():
    SentimentAnalyzer.reset_instance()
    mock_tok_instance = MockTokenizer()
    mock_model_instance = MockModel()
    
    with patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tok_instance), \
         patch("transformers.AutoModelForSequenceClassification.from_pretrained", return_value=mock_model_instance):
        yield
        SentimentAnalyzer.reset_instance()
