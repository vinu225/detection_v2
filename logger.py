"""
logger.py — Centralized logging configuration.
Writes to stdout (for containers/dev) and to logs/app.log simultaneously.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = "news_pipeline",
    log_level: str = "INFO",
    log_file: str = "logs/app.log",
) -> logging.Logger:
    """
    Configure and return an application logger with console + file handlers.
    Safe to call multiple times — handlers are not duplicated.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers twice (e.g. on reload in uvicorn --reload mode)
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # ── Rotating file handler ─────────────────────────────────────────────────
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Could not create log file %s: %s", log_file, exc)

    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """Return a child logger scoped to the calling module."""
    from config import get_settings

    settings = get_settings()
    root = setup_logger(log_level=settings.log_level, log_file=settings.log_file)
    if module_name:
        return root.getChild(module_name)
    return root
