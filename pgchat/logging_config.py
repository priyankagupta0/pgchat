"""Simple centralized logging configuration for PgChat."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pgchat.config import CONFIG_DIR

# Log file configuration
LOG_DIR = CONFIG_DIR / "logs"
LOG_FILE = LOG_DIR / "pgchat.log"

# Simple configuration
_configured = False


def setup_logging(console_level: str = "INFO", enable_file: bool = True) -> None:
    """
    Configure logging for PgChat application.

    Args:
        console_level: Console log level (INFO, DEBUG, WARNING, ERROR).
        enable_file: Whether to enable file logging with rotation.

    Environment Variables:
        PGCHAT_LOG_LEVEL: Override console log level
        PGCHAT_DISABLE_FILE_LOG: Set to '1' to disable file logging
    """
    global _configured
    if _configured:
        return

    # Check environment overrides
    console_level = os.getenv("PGCHAT_LOG_LEVEL", console_level).upper()
    enable_file = enable_file and os.getenv("PGCHAT_DISABLE_FILE_LOG") != "1"

    # Configure root pgchat logger
    logger = logging.getLogger("pgchat")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, console_level, logging.INFO))
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler with rotation
    if enable_file:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module.

    Args:
        name: Module name, typically __name__.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
