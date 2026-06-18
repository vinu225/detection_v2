"""
module_2/tests/test_preprocessing.py — Unit tests for preprocessor.py.
"""

from module_2_sentimental.preprocessor import clean_text

def test_clean_text_basic():
    text = "Hello world."
    assert clean_text(text) == "Hello world."

def test_clean_text_unicode_quotes():
    text = "\u201cHello\u201d and \u2018world\u2019 \u2014 test"
    cleaned = clean_text(text)
    assert '"Hello"' in cleaned
    assert "'world'" in cleaned
    assert "-" in cleaned

def test_clean_text_urls():
    text = "Visit https://google.com or http://example.com/page?id=123 for details."
    cleaned = clean_text(text)
    assert "https://google.com" not in cleaned
    assert "http://example.com" not in cleaned
    assert "Visit or for details." in cleaned

def test_clean_text_excessive_punctuation():
    text = "Wow!!! Really??? This is a test..."
    cleaned = clean_text(text)
    assert "Wow!" in cleaned
    assert "Really?" in cleaned
    # Ellipsis should be preserved
    assert "test..." in cleaned

def test_clean_text_whitespace():
    text = "Hello    world.\n\n\n\nNew   paragraph."
    cleaned = clean_text(text)
    assert "Hello world." in cleaned
    assert "New paragraph." in cleaned
    assert "\n\n" in cleaned
    assert "\n\n\n" not in cleaned

def test_clean_text_invalid_characters():
    # Remove chars like emojis or random control codes but keep standard chars
    text = "Price is $100 and €50. Emoji here: 🚀."
    cleaned = clean_text(text)
    assert "$100" in cleaned
    assert "€50" in cleaned
    assert "🚀" not in cleaned

def test_clean_text_empty_and_none():
    assert clean_text("") == ""
    assert clean_text(None) == ""

def test_clean_text_control_characters():
    # Null byte \x00, control code \x07, zero-width space \u200b
    text = "Hello\x00 world\x07.\u200b"
    cleaned = clean_text(text)
    assert cleaned == "Hello world."
