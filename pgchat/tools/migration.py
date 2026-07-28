from __future__ import annotations

from datetime import datetime, timezone

from pgchat.db import pool
from pgchat.tools.format import dumps, rows_to_dicts

_ENSURE_TABLE = """
CREATE TABLE IF NOT EXISTS pgchat_migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    sql TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rolled_back_at TIMESTAMPTZ,
    rollback_sql TEXT
);
"""


async def _ensure(conn) -> None:
    await conn.execute(_ENSURE_TABLE)


async def apply_migration(name: str, sql: str, rollback_sql: str | None = None) -> str:
    """Apply a named migration SQL script and record it in pgchat_migrations."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        await _ensure(conn)
        async with conn.transaction():
            await conn.execute(sql)
            row = await conn.fetchrow(
                """
                INSERT INTO pgchat_migrations (name, sql, rollback_sql)
                VALUES ($1, $2, $3)
                RETURNING id, name, applied_at
                """,
                name,
                sql,
                rollback_sql,
            )
    return dumps({"status": "applied", "migration": dict(row)})


async def rollback_migration(migration_id: int | None = None, name: str | None = None) -> str:
    """Rollback the latest (or specified) migration using stored rollback_sql."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        await _ensure(conn)
        if migration_id is not None:
            row = await conn.fetchrow(
                "SELECT * FROM pgchat_migrations WHERE id = $1 AND rolled_back_at IS NULL",
                migration_id,
            )
        elif name is not None:
            row = await conn.fetchrow(
                """
                SELECT * FROM pgchat_migrations
                WHERE name = $1 AND rolled_back_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                name,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT * FROM pgchat_migrations
                WHERE rolled_back_at IS NULL
                ORDER BY id DESC LIMIT 1
                """
            )
        if not row:
            return dumps({"error": "No applied migration found to rollback"})
        if not row["rollback_sql"]:
            return dumps(
                {
                    "error": "Migration has no rollback_sql recorded",
                    "migration_id": row["id"],
                    "name": row["name"],
                }
            )
        async with conn.transaction():
            await conn.execute(row["rollback_sql"])
            await conn.execute(
                "UPDATE pgchat_migrations SET rolled_back_at = $1 WHERE id = $2",
                datetime.now(timezone.utc),
                row["id"],
            )
    return dumps({"status": "rolled_back", "migration_id": row["id"], "name": row["name"]})


async def list_migrations(limit: int = 50) -> str:
    """List recorded migrations."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        await _ensure(conn)
        rows = await conn.fetch(
            """
            SELECT id, name, applied_at, rolled_back_at,
                   (rollback_sql IS NOT NULL) AS has_rollback
            FROM pgchat_migrations
            ORDER BY id DESC
            LIMIT $1
            """,
            limit,
        )
    return dumps({"migrations": rows_to_dicts(rows)})
