"""Pytest configuration and fixtures."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before each test."""
    # Clear pgchat logger handlers
    logger = logging.getLogger("pgchat")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)

    # Reset configuration flag
    import pgchat.logging_config as lc
    lc._configured = False

    yield

    # Cleanup after test
    logger.handlers.clear()
    lc._configured = False


@pytest.fixture
def sample_query_result():
    """Fixture providing a sample QueryResult for testing."""
    from pgchat.tools.query import QueryResult

    return QueryResult(
        columns=["id", "name", "email"],
        rows=[
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
        ],
        row_count=3,
        duration_ms=25.5,
        truncated=False,
    )


@pytest.fixture
def error_query_result():
    """Fixture providing an error QueryResult for testing."""
    from pgchat.tools.query import QueryResult

    return QueryResult(
        columns=[],
        rows=[],
        row_count=0,
        duration_ms=0.0,
        truncated=False,
        error={
            "code": "READ_ONLY_VIOLATION",
            "message": "Only read-only queries are allowed",
            "hint": "Use SELECT, WITH, SHOW, or EXPLAIN",
        },
    )
