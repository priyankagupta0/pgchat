"""Basic sanity test - removed in favor of comprehensive test suite.

See:
- test_query.py for query execution and read-only enforcement tests
- test_config.py for configuration tests
- test_logging.py for logging tests
- test_render.py for UI rendering tests
"""

import pytest


def test_import_main_modules():
    """Test that main modules can be imported without errors."""
    from pgchat import __version__
    from pgchat.config import Settings
    from pgchat.logging_config import get_logger
    from pgchat.tools.query import QueryResult, is_readonly_sql
    from pgchat.ui.render import QueryRenderer

    assert __version__ == "0.1.0"
    assert Settings is not None
    assert get_logger is not None
    assert QueryResult is not None
    assert is_readonly_sql is not None
    assert QueryRenderer is not None


def test_readonly_detection_basic():
    """Basic test that readonly detection works."""
    from pgchat.tools.query import is_readonly_sql

    # Safe queries
    assert is_readonly_sql("SELECT * FROM users")
    assert is_readonly_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")

    # Dangerous queries
    assert not is_readonly_sql("INSERT INTO users VALUES (1)")
    assert not is_readonly_sql("UPDATE users SET name = 'x'")
    assert not is_readonly_sql("DELETE FROM users")
    assert not is_readonly_sql("DROP TABLE users")
