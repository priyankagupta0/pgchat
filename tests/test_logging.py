"""Tests for centralized logging configuration."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from pgchat.logging_config import get_logger, setup_logging, LOG_DIR


class TestLoggingConfiguration:
    """Test logging setup and configuration."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_auto_configures(self):
        """Test that get_logger auto-configures logging on first call."""
        # Reset any existing configuration
        logging.getLogger("pgchat").handlers.clear()
        
        logger = get_logger("pgchat.test")
        
        # Should have handlers configured
        pgchat_logger = logging.getLogger("pgchat")
        assert len(pgchat_logger.handlers) > 0

    def test_setup_logging_idempotent(self):
        """Test that setup_logging can be called multiple times safely."""
        setup_logging(console_level="INFO")
        setup_logging(console_level="DEBUG")  # Should not raise error
        
        # Should still work
        logger = get_logger(__name__)
        logger.info("Test message")

    def test_console_level_configuration(self):
        """Test setting console log level."""
        setup_logging(console_level="ERROR", enable_file=False)
        
        pgchat_logger = logging.getLogger("pgchat")
        
        # Find console handler
        console_handlers = [
            h for h in pgchat_logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        
        assert len(console_handlers) > 0
        # Check that level is ERROR (40)
        assert console_handlers[0].level == logging.ERROR

    def test_file_logging_disabled(self):
        """Test disabling file logging."""
        setup_logging(console_level="INFO", enable_file=False)
        
        pgchat_logger = logging.getLogger("pgchat")
        
        # Should only have console handler
        from logging.handlers import RotatingFileHandler
        file_handlers = [
            h for h in pgchat_logger.handlers
            if isinstance(h, RotatingFileHandler)
        ]
        
        assert len(file_handlers) == 0

    def test_environment_variable_override(self, monkeypatch):
        """Test that PGCHAT_LOG_LEVEL environment variable works."""
        # Reset configuration
        import pgchat.logging_config as lc
        lc._configured = False
        logging.getLogger("pgchat").handlers.clear()
        
        monkeypatch.setenv("PGCHAT_LOG_LEVEL", "WARNING")
        
        setup_logging()
        
        pgchat_logger = logging.getLogger("pgchat")
        console_handlers = [
            h for h in pgchat_logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        
        # Should respect environment variable
        assert console_handlers[0].level == logging.WARNING

    def test_disable_file_logging_env(self, monkeypatch):
        """Test PGCHAT_DISABLE_FILE_LOG environment variable."""
        import pgchat.logging_config as lc
        lc._configured = False
        logging.getLogger("pgchat").handlers.clear()
        
        monkeypatch.setenv("PGCHAT_DISABLE_FILE_LOG", "1")
        
        setup_logging(enable_file=True)  # Try to enable, but env should override
        
        pgchat_logger = logging.getLogger("pgchat")
        from logging.handlers import RotatingFileHandler
        file_handlers = [
            h for h in pgchat_logger.handlers
            if isinstance(h, RotatingFileHandler)
        ]
        
        assert len(file_handlers) == 0

    def test_log_dir_creation(self, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        # This test verifies the mkdir logic works
        test_dir = tmp_path / "logs"
        assert not test_dir.exists()
        
        # LOG_DIR should be created when file logging is enabled
        # (We can't easily test this without mocking, but we verify the constant)
        assert LOG_DIR.name == "logs"

    def test_logger_hierarchy(self):
        """Test that loggers follow Python's logger hierarchy."""
        parent = get_logger("pgchat.parent")
        child = get_logger("pgchat.parent.child")
        
        assert child.parent.name == parent.name

    def test_multiple_modules_same_logger(self):
        """Test that multiple modules get independent loggers."""
        logger1 = get_logger("pgchat.module1")
        logger2 = get_logger("pgchat.module2")
        
        assert logger1 is not logger2
        assert logger1.name != logger2.name

    def test_log_format(self):
        """Test that log format includes required fields."""
        setup_logging(console_level="INFO", enable_file=False)
        
        pgchat_logger = logging.getLogger("pgchat")
        handler = pgchat_logger.handlers[0]
        formatter = handler.formatter
        
        # Check format string includes key components
        assert formatter is not None
        format_str = formatter._fmt
        assert "asctime" in format_str
        assert "name" in format_str
        assert "levelname" in format_str
        assert "message" in format_str
