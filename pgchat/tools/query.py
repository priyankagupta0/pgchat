"""SQL query execution with read-only enforcement and safety measures."""

from __future__ import annotations
import asyncpg
import re
import time
from typing import Any

from pydantic import BaseModel

from pgchat.db.pool import Database
from pgchat.logging_config import get_logger

logger = get_logger(__name__)

# More robust readonly detection (still defense-in-depth only)
READONLY_PREFIXES = ("select", "with", "show", "explain", "values", "describe")
BLOCKED_KEYWORDS = {
    "insert", "update", "delete", "drop", "truncate", "alter", "create",
    "grant", "revoke", "vacuum", "reindex", "copy", "call", "do", "execute"
}

class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    duration_ms: float
    truncated: bool
    error: dict[str, Any] | None = None


def is_readonly_sql(sql: str) -> bool:
    """Fast, normalized check. Not perfect — we still use DB-level protection."""
    normalized = re.sub(r'--.*$|/\*.*?\*/', '', sql, flags=re.MULTILINE | re.DOTALL)
    normalized = normalized.strip().lower()

    if not normalized:
        return False

    first_word = normalized.split(maxsplit=1)[0]
    if first_word not in READONLY_PREFIXES:
        return False

    tokens = set(re.findall(r'\b\w+\b', normalized))
    return not (tokens & BLOCKED_KEYWORDS)


async def run_query(sql: str, limit: int = 100) -> QueryResult:
    """
    Secure, read-only query executor.
    """
    logger.debug(f"Received query request with limit {limit}: {sql[:100]}...")

    if not is_readonly_sql(sql):
        logger.warning(f"Rejected non-readonly query: {sql[:50]}...")
        return QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            duration_ms=0.0,
            truncated=False,
            error={
                "code": "READ_ONLY_VIOLATION",
                "message": "Only read-only queries are allowed (SELECT, WITH, SHOW, EXPLAIN, VALUES, DESCRIBE).",
                "hint": "Write operations are blocked at both app and database level.",
            }
        )

    pool = Database.get_pool()
    started = time.perf_counter()

    try:
        async with pool.acquire() as conn:
            # Strong defense: Transaction-level + Role-level (best practice)
            await conn.execute("SET TRANSACTION READ ONLY;")
            await conn.execute("SET statement_timeout = '30s';")   # Hard limit

            effective_limit = max(1, min(limit, 1000))
            logger.debug(f"Executing query with effective limit: {effective_limit}")

            wrapped_sql = """
                SELECT * FROM (
                    SELECT * FROM ({}) AS subq
                ) AS pgchat_wrapper
                LIMIT $1
            """.format(sql.rstrip("; \n\t"))

            records = await conn.fetch(wrapped_sql, effective_limit + 1)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        truncated = len(records) > effective_limit
        visible = records[:effective_limit]

        rows = [dict(r) for r in visible]          # asyncpg Record supports dict()
        columns = list(rows[0].keys()) if rows else []

        logger.info(
            f"Query executed successfully: {len(rows)} rows returned in {duration_ms}ms "
            f"(truncated={truncated})"
        )

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            duration_ms=duration_ms,
            truncated=truncated,
        )

    except asyncpg.exceptions.PostgresError as e:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.error(f"Postgres error during query execution: {type(e).__name__} - {e}")
        return QueryResult(
            columns=[], rows=[], row_count=0, duration_ms=duration_ms, truncated=False,
            error={
                "code": type(e).__name__,
                "message": str(e),
                "retryable": isinstance(e, (asyncpg.exceptions.ConnectionDoesNotExistError,
                                           asyncpg.exceptions.TooManyConnectionsError))
            }
        )
    except Exception as e:   # Catch unexpected errors
        logger.exception(f"Unexpected error during query execution: {e}")
        return QueryResult(
            columns=[], rows=[], row_count=0, duration_ms=0.0, truncated=False,
            error={"code": "INTERNAL_ERROR", "message": "Query execution failed"}
        )