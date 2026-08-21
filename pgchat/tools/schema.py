from __future__ import annotations

import json
import time
from pathlib import Path

from pgchat.config import SCHEMA_CACHE_DIR
from pgchat.db import pool
from pgchat.tools.format import dumps, rows_to_dicts

_CACHE_TTL_SEC = 300


def _cache_file(database: str) -> Path:
    SCHEMA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in database)
    return SCHEMA_CACHE_DIR / f"{safe}.json"


async def list_tables(schema: str | None = None) -> str:
    """List tables and views in a schema (default: configured schema)."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_type, table_name
            """,
            schema,
        )
    return dumps({"schema": schema, "tables": rows_to_dicts(rows)})


async def describe_table(table: str, schema: str | None = None) -> str:
    """Describe columns, nullability, and defaults for a table."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    async with db.acquire() as conn:
        cols = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default,
                   character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema,
            table,
        )
        pks = await conn.fetch(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = $1 AND tc.table_name = $2
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
            """,
            schema,
            table,
        )
        fks = await conn.fetch(
            """
            SELECT
              kcu.column_name,
              ccu.table_schema AS foreign_table_schema,
              ccu.table_name AS foreign_table_name,
              ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.table_schema = $1 AND tc.table_name = $2
              AND tc.constraint_type = 'FOREIGN KEY'
            """,
            schema,
            table,
        )
    return dumps(
        {
            "schema": schema,
            "table": table,
            "columns": rows_to_dicts(cols),
            "primary_key": [r["column_name"] for r in pks],
            "foreign_keys": rows_to_dicts(fks),
        }
    )


async def list_indexes(table: str, schema: str | None = None) -> str:
    """List indexes for a table."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = $1 AND tablename = $2
            ORDER BY indexname
            """,
            schema,
            table,
        )
    return dumps({"schema": schema, "table": table, "indexes": rows_to_dicts(rows)})


async def get_table_stats(table: str | None = None, schema: str | None = None) -> str:
    """Return size and row estimates for one table or all tables in a schema."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    async with db.acquire() as conn:
        if table:
            row = await conn.fetchrow(
                """
                SELECT
                  c.relname AS table,
                  n.nspname AS schema,
                  c.reltuples::bigint AS estimated_rows,
                  pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                  pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
                  pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = $1 AND c.relname = $2 AND c.relkind = 'r'
                """,
                schema,
                table,
            )
            return dumps({"stats": dict(row) if row else None})
        rows = await conn.fetch(
            """
            SELECT
              c.relname AS table,
              c.reltuples::bigint AS estimated_rows,
              pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 100
            """,
            schema,
        )
    return dumps({"schema": schema, "tables": rows_to_dicts(rows)})


async def refresh_schema_cache(schema: str | None = None) -> str:
    """Cache table/column metadata locally for faster agent grounding."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    tables_json = await list_tables(schema)
    tables = json.loads(tables_json)["tables"]
    details = []
    for t in tables:
        if t["table_type"] != "BASE TABLE":
            continue
        desc = json.loads(await describe_table(t["table_name"], schema))
        details.append(desc)
    payload = {
        "database": cfg.database.database,
        "schema": schema,
        "cached_at": time.time(),
        "tables": details,
    }
    path = _cache_file(cfg.database.database)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dumps({"cached_tables": len(details), "path": str(path)})


async def get_schema_cache() -> str:
    """Return the local schema cache if fresh, otherwise refresh it."""
    cfg = pool.get_config()
    path = _cache_file(cfg.database.database)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("cached_at", 0))
        if age < _CACHE_TTL_SEC:
            return dumps({"fresh": True, "age_seconds": int(age), "cache": data})
    refreshed = json.loads(await refresh_schema_cache())
    data = json.loads(path.read_text(encoding="utf-8"))
    return dumps({"fresh": False, "refreshed": refreshed, "cache": data})
