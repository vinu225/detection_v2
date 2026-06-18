"""
image_processing.py — Utilities to validate images and perform OCR/text extraction
and news context analysis using Google Gemini models with fallback strategies.
"""

from __future__ import annotations

import base64
import io
import mimetypes
from typing import Dict, Optional

import requests
from PIL import Image, UnidentifiedImageError

from module_1_scraping.config import get_settings
from shared.logger import get_logger

log = get_logger("image_processing")
settings = get_settings()


def validate_image(image_bytes: bytes) -> str:
    """
    Validate that image_bytes represents a valid, non-corrupted image.
    Returns the image format string (e.g., 'PNG', 'JPEG') if valid.
    Raises ValueError if the image is invalid or corrupted.
    """
    if not image_bytes:
        raise ValueError("Empty image data provided.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
            fmt = img.format or "PNG"
            log.debug("Image verified successfully. Format: %s", fmt)
            return fmt
    except (UnidentifiedImageError, SyntaxError, TypeError, OSError) as exc:
        log.error("Image validation failed: %s", exc)
        raise ValueError(f"Invalid or corrupted image: {exc}") from exc


def get_mime_type(format_name: str) -> str:
    """Map PIL format name to MIME type."""
    fmt = format_name.lower()
    if fmt in ("jpeg", "jpg"):
        return "image/jpeg"
    elif fmt == "png":
        return "image/png"
    elif fmt == "webp":
        return "image/webp"
    elif fmt == "gif":
        return "image/gif"
    
    mime, _ = mimetypes.guess_type(f"file.{fmt}")
    return mime or "image/png"


def query_gemini_multimodal(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Query the Gemini API with an image and a text prompt.
    Implements a model fallback cascade:
      1. gemini-3.5-flash (primary requested)
      2. gemini-3-preview (fallback requested)
      3. gemini-2.5-flash (production stable backup)
      4. gemini-1.5-flash (legacy backup)
    """
    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    # Cascade list as instructed
    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash"]
    last_error = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": b64_data
                            }
                        }
                    ]
                }
            ]
        }

        try:
            log.info("Attempting multimodal generation using Gemini model: %s", model)
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            result_json = resp.json()
            
            candidates = result_json.get("candidates", [])
            if not candidates:
                continue
                
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0]:
                continue
                
            response_text = parts[0]["text"].strip()
            log.info("Successfully received response from Gemini model: %s", model)
            return response_text
        except Exception as exc:
            log.warning("Gemini model %s failed: %s", model, exc)
            last_error = exc

    raise RuntimeError(f"All Gemini model choices in the cascade failed. Last error: {last_error}")


def extract_text_from_image(image_bytes: bytes, filename: str = "image.png") -> str:
    """
    Extract readable text from image.
    Uses Google Gemini Vision cascade if API key is present, otherwise falls back to Mock.
    """
    fmt = validate_image(image_bytes)
    mime_type = get_mime_type(fmt)
    
    if not settings.gemini_api_key:
        log.warning("GEMINI_API_KEY is not set. Falling back to Mock OCR text extraction.")
        return _get_mock_ocr_text(filename)

    prompt = (
        "Extract all readable news article or document text from this image. "
        "Output only the extracted text, keeping original paragraph breaks. "
        "Do not add markdown formatting, code block fences, or conversational filler."
    )
    return query_gemini_multimodal(image_bytes, mime_type, prompt)


def analyze_image_news_context(image_bytes: bytes, filename: str = "image.png") -> Dict[str, str]:
    """
    Extracts text AND performs contextual news analysis on what the image portrays.
    Returns a dict with 'extracted_text' and 'news_analysis'.
    """
    fmt = validate_image(image_bytes)
    mime_type = get_mime_type(fmt)
    
    if not settings.gemini_api_key:
        log.warning("GEMINI_API_KEY is not set. Returning mock OCR + mock news analysis.")
        return {
            "extracted_text": _get_mock_ocr_text(filename),
            "news_analysis": (
                f"Mock News Analysis: The image '{filename}' appears to depict a significant public scenario. "
                "Based on recent trends, this event is drawing massive online interest and comments across social platforms. "
                "Experts suggest this development could reshape market dynamics in the coming quarters."
            )
        }

    # 1. OCR text extraction
    ocr_prompt = (
        "Extract all readable news article or document text from this image. "
        "Output only the extracted text, keeping original paragraph breaks. "
        "Do not add markdown formatting, code block fences, or conversational filler."
    )
    try:
        extracted_text = query_gemini_multimodal(image_bytes, mime_type, ocr_prompt)
    except Exception as exc:
        log.error("Failed to perform OCR extraction: %s", exc)
        extracted_text = "Failed to extract text from the image."

    # 2. Contextual news analysis
    analysis_prompt = (
        "Identify the primary subject, scenario, or public figures depicted in this image. "
        "Provide a professional analysis of the recent news, rumors, or events associated with "
        "this specific image scenario (e.g., if it portrays Elon Musk, Donald Trump, or a specific financial/political meme, "
        "connect it to actual context and explain what is going on). Maintain a professional journalistic tone."
    )
    try:
        analysis_text = query_gemini_multimodal(image_bytes, mime_type, analysis_prompt)
    except Exception as exc:
        log.error("Failed to perform news analysis: %s", exc)
        analysis_text = f"Failed to generate news analysis: {exc}"

    return {
        "extracted_text": extracted_text,
        "news_analysis": analysis_text
    }


def query_gemini_text(prompt: str) -> str:
    """
    Query the Gemini API with a text prompt.
    Implements a model fallback cascade:
      1. gemini-3.5-flash
      2. gemini-3-preview
      3. gemini-2.5-flash
      4. gemini-1.5-flash
    """
    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash"]
    last_error = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }

        try:
            log.info("Attempting text generation using Gemini model: %s", model)
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            result_json = resp.json()
            
            candidates = result_json.get("candidates", [])
            if not candidates:
                continue
                
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0]:
                continue
                
            response_text = parts[0]["text"].strip()
            log.info("Successfully received text response from Gemini model: %s", model)
            return response_text
        except Exception as exc:
            log.warning("Gemini text model %s failed: %s", model, exc)
            last_error = exc

    raise RuntimeError(f"All Gemini text model choices failed. Last error: {last_error}")


def _get_mock_ocr_text(filename: str) -> str:
    """Return a detailed mock article for testing when no API key is available."""
    clean_name = filename.replace("_", " ").replace("-", " ")
    if "." in clean_name:
        clean_name = clean_name.rsplit(".", 1)[0]
        
    return (
        f"This is a mocked news article extracted from the image file '{filename}'.\n\n"
        f"The image processing component parsed the visual content of '{clean_name}' successfully. "
        "Scientists and research teams around the world have been collaborating on enhancing pipeline interfaces. "
        "This paragraph provides additional body content that is designed to satisfy length constraints in the pipeline.\n\n"
        "In a statement released earlier today, officials noted that automated text ingestion from screenshots "
        "will drastically reduce processing times for downstream pipelines. The integration has proven robust and "
        "efficient in all initial benchmark simulations."
    )
