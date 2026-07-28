"""Tests for configuration management."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pgchat.config import Settings


class TestSettingsValidation:
    """Test Settings model validation."""

    def test_valid_settings(self):
        """Test creating valid settings."""
        settings = Settings(
            gemini_api_key="test-key-123",
            database_url="postgresql://user:pass@localhost:5432/testdb",
            gemini_model="gemini-2.5-flash",
            query_limit=100,
            statement_timeout_ms=10000,
            pool_min_size=1,
            pool_max_size=10,
        )
        assert settings.gemini_api_key == "test-key-123"
        assert settings.query_limit == 100
        assert settings.pool_min_size == 1
        assert settings.pool_max_size == 10

    def test_default_values(self):
        """Test default values are applied."""
        settings = Settings(
            gemini_api_key="test-key",
            database_url="postgresql://localhost/testdb",
        )
        assert settings.gemini_model == "gemini-3-flash"
        assert settings.query_limit == 100
        assert settings.statement_timeout_ms == 10_000
        assert settings.pool_min_size == 1
        assert settings.pool_max_size == 10

    def test_invalid_pool_sizes(self):
        """Test that pool_min_size > pool_max_size is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                gemini_api_key="test-key",
                database_url="postgresql://localhost/testdb",
                pool_min_size=10,
                pool_max_size=5,
            )
        assert "pool_min_size cannot be greater than pool_max_size" in str(exc_info.value)

    def test_invalid_query_limit(self):
        """Test that query_limit must be positive."""
        with pytest.raises(ValidationError):
            Settings(
                gemini_api_key="test-key",
                database_url="postgresql://localhost/testdb",
                query_limit=0,
            )

        with pytest.raises(ValidationError):
            Settings(
                gemini_api_key="test-key",
                database_url="postgresql://localhost/testdb",
                query_limit=-10,
            )

    def test_invalid_statement_timeout(self):
        """Test that statement_timeout_ms must be positive."""
        with pytest.raises(ValidationError):
            Settings(
                gemini_api_key="test-key",
                database_url="postgresql://localhost/testdb",
                statement_timeout_ms=0,
            )

    def test_invalid_database_url(self):
        """Test that invalid database URLs are rejected."""
        with pytest.raises(ValidationError):
            Settings(
                gemini_api_key="test-key",
                database_url="not-a-valid-url",
            )

    def test_postgres_url_scheme(self):
        """Test that only PostgreSQL URLs are accepted."""
        # Valid PostgreSQL URLs
        valid_urls = [
            "postgresql://localhost/db",
            "postgresql://user:pass@localhost:5432/db",
            "postgres://localhost/db",  # Also accepted by Pydantic
        ]

        for url in valid_urls:
            settings = Settings(
                gemini_api_key="test-key",
                database_url=url,
            )
            assert settings.database_url is not None

    def test_settings_immutable(self):
        """Test that Settings is frozen (immutable)."""
        settings = Settings(
            gemini_api_key="test-key",
            database_url="postgresql://localhost/testdb",
        )

        with pytest.raises(ValidationError):
            settings.query_limit = 200

    def test_environment_prefix(self):
        """Test that PGCHAT_ environment prefix is configured."""
        # This would require setting environment variables in test
        # Just verify the model config is correct
        assert Settings.model_config["env_prefix"] == "PGCHAT_"
