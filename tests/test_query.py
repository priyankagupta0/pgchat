"""Tests for SQL query execution and read-only enforcement."""

from __future__ import annotations

import pytest

from pgchat.tools.query import BLOCKED_KEYWORDS, READONLY_PREFIXES, QueryResult, is_readonly_sql


class TestReadOnlyDetection:
    """Test the read-only SQL detection logic."""

    def test_select_queries_allowed(self):
        """SELECT queries should be allowed."""
        assert is_readonly_sql("SELECT * FROM users")
        assert is_readonly_sql("SELECT id, name FROM products WHERE active = true")
        assert is_readonly_sql("select * from orders")  # lowercase
        assert is_readonly_sql("  SELECT  *  FROM  items  ")  # whitespace

    def test_with_cte_allowed(self):
        """WITH (CTE) queries should be allowed."""
        assert is_readonly_sql("WITH cte AS (SELECT * FROM users) SELECT * FROM cte")
        assert is_readonly_sql("with recursive tree as (select * from nodes) select * from tree")

    def test_show_allowed(self):
        """SHOW statements should be allowed."""
        assert is_readonly_sql("SHOW server_version")
        assert is_readonly_sql("SHOW timezone")

    def test_explain_allowed(self):
        """EXPLAIN statements should be allowed."""
        assert is_readonly_sql("EXPLAIN SELECT * FROM users")
        assert is_readonly_sql("EXPLAIN ANALYZE SELECT * FROM large_table")

    def test_values_allowed(self):
        """VALUES statements should be allowed."""
        assert is_readonly_sql("VALUES (1, 'test'), (2, 'data')")

    def test_insert_blocked(self):
        """INSERT queries should be blocked."""
        assert not is_readonly_sql("INSERT INTO users (name) VALUES ('test')")
        assert not is_readonly_sql("insert into products values (1, 'item')")

    def test_update_blocked(self):
        """UPDATE queries should be blocked."""
        assert not is_readonly_sql("UPDATE users SET name = 'new' WHERE id = 1")
        assert not is_readonly_sql("update products set price = 100")

    def test_delete_blocked(self):
        """DELETE queries should be blocked."""
        assert not is_readonly_sql("DELETE FROM users WHERE id = 1")
        assert not is_readonly_sql("delete from orders")

    def test_drop_blocked(self):
        """DROP statements should be blocked."""
        assert not is_readonly_sql("DROP TABLE users")
        assert not is_readonly_sql("DROP DATABASE testdb")

    def test_truncate_blocked(self):
        """TRUNCATE statements should be blocked."""
        assert not is_readonly_sql("TRUNCATE TABLE users")

    def test_alter_blocked(self):
        """ALTER statements should be blocked."""
        assert not is_readonly_sql("ALTER TABLE users ADD COLUMN age INT")
        assert not is_readonly_sql("alter table products drop column price")

    def test_create_blocked(self):
        """CREATE statements should be blocked."""
        assert not is_readonly_sql("CREATE TABLE test (id INT)")
        assert not is_readonly_sql("CREATE INDEX idx ON users(name)")

    def test_grant_revoke_blocked(self):
        """GRANT/REVOKE statements should be blocked."""
        assert not is_readonly_sql("GRANT SELECT ON users TO user")
        assert not is_readonly_sql("REVOKE ALL ON database FROM user")

    def test_comments_ignored(self):
        """SQL comments should be ignored in detection."""
        assert is_readonly_sql("-- INSERT comment\nSELECT * FROM users")
        assert is_readonly_sql("/* INSERT block comment */ SELECT * FROM users")

    def test_empty_query(self):
        """Empty queries should be rejected."""
        assert not is_readonly_sql("")
        assert not is_readonly_sql("   ")
        assert not is_readonly_sql("\n\t")

    def test_nested_write_blocked(self):
        """Write operations in nested queries should be blocked."""
        # Token-based detection should catch this
        assert not is_readonly_sql("SELECT * FROM (INSERT INTO users VALUES (1)) AS x")

    def test_constants_coverage(self):
        """Verify all blocked keywords and prefixes are defined."""
        assert "insert" in BLOCKED_KEYWORDS
        assert "update" in BLOCKED_KEYWORDS
        assert "delete" in BLOCKED_KEYWORDS
        assert "select" in READONLY_PREFIXES
        assert "with" in READONLY_PREFIXES


class TestQueryResult:
    """Test QueryResult Pydantic model."""

    def test_successful_result(self):
        """Test creating a successful query result."""
        result = QueryResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            row_count=2,
            duration_ms=15.5,
            truncated=False,
        )
        assert result.columns == ["id", "name"]
        assert result.row_count == 2
        assert result.duration_ms == 15.5
        assert not result.truncated
        assert result.error is None

    def test_error_result(self):
        """Test creating an error query result."""
        result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            duration_ms=0.0,
            truncated=False,
            error={
                "code": "READ_ONLY_VIOLATION",
                "message": "Write operations not allowed",
            },
        )
        assert result.error is not None
        assert result.error["code"] == "READ_ONLY_VIOLATION"
        assert result.row_count == 0

    def test_truncated_result(self):
        """Test creating a truncated query result."""
        result = QueryResult(
            columns=["id"],
            rows=[{"id": i} for i in range(100)],
            row_count=100,
            duration_ms=50.0,
            truncated=True,
        )
        assert result.truncated
        assert result.row_count == 100

    def test_serialization(self):
        """Test Pydantic model serialization."""
        result = QueryResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            duration_ms=10.0,
            truncated=False,
        )
        serialized = result.model_dump()
        assert "columns" in serialized
        assert "rows" in serialized
        assert "error" in serialized
        assert serialized["error"] is None


class TestQueryExecution:
    """Test actual query execution (requires database)."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires live database connection")
    async def test_run_query_success(self):
        """Test successful query execution."""
        # This would require a test database setup
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires live database connection")
    async def test_run_query_limit(self):
        """Test query result limiting."""
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires live database connection")
    async def test_run_query_readonly_enforcement(self):
        """Test database-level read-only enforcement."""
        pass
