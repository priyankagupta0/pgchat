from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp.server.fastmcp import FastMCP

from pgchat.config import load_config
from pgchat.db import pool
from pgchat.tools import admin, migration, performance, query, schema


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    config_path = os.environ.get("PGCHAT_CONFIG")
    cfg = load_config(Path(config_path)) if config_path else load_config()
    await pool.init_pool(cfg)
    try:
        yield {"config": cfg}
    finally:
        await pool.close_pool()


mcp = FastMCP(
    "pgchat",
    instructions=(
        "PostgreSQL database operator tools. Prefer read-only inspection first. "
        "Use migrations for schema changes. Ask for confirmation before destructive ops."
    ),
    lifespan=lifespan,
)


@mcp.tool()
async def run_query(sql: str, limit: int | None = None) -> str:
    """Execute a PostgreSQL statement. SELECT results return JSON rows (capped)."""
    return await query.run_query(sql, limit=limit)


@mcp.tool()
async def explain_query(sql: str, analyze: bool = False) -> str:
    """Run EXPLAIN (optionally ANALYZE) on a SQL statement and return the plan JSON."""
    return await query.explain_query(sql, analyze=analyze)


@mcp.tool()
async def list_tables(schema: str | None = None) -> str:
    """List tables and views in a schema."""
    return await schema.list_tables(schema=schema)


@mcp.tool()
async def describe_table(table: str, schema: str | None = None) -> str:
    """Describe columns, primary keys, and foreign keys for a table."""
    return await schema.describe_table(table, schema=schema)


@mcp.tool()
async def list_indexes(table: str, schema: str | None = None) -> str:
    """List indexes defined on a table."""
    return await schema.list_indexes(table, schema=schema)


@mcp.tool()
async def get_table_stats(table: str | None = None, schema: str | None = None) -> str:
    """Return size and estimated row counts for a table or all tables in a schema."""
    return await schema.get_table_stats(table=table, schema=schema)


@mcp.tool()
async def get_schema_cache() -> str:
    """Return cached schema metadata (auto-refreshes after TTL)."""
    return await schema.get_schema_cache()


@mcp.tool()
async def refresh_schema_cache(schema: str | None = None) -> str:
    """Rebuild the local schema cache for the database."""
    return await schema.refresh_schema_cache(schema=schema)


@mcp.tool()
async def get_slow_queries(limit: int = 20, min_calls: int = 5) -> str:
    """Return the slowest queries from pg_stat_statements when available."""
    return await performance.get_slow_queries(limit=limit, min_calls=min_calls)


@mcp.tool()
async def suggest_indexes(table: str, schema: str | None = None) -> str:
    """Suggest indexes from seq-scan pressure, missing FK indexes, and unused indexes."""
    return await performance.suggest_indexes(table, schema=schema)


@mcp.tool()
async def create_index(
    table: str,
    columns: str,
    schema: str | None = None,
    unique: bool = False,
    concurrently: bool = True,
    name: str | None = None,
) -> str:
    """Create an index. columns is a comma-separated list of column names."""
    return await performance.create_index(
        table, columns, schema=schema, unique=unique, concurrently=concurrently, name=name
    )


@mcp.tool()
async def drop_index(
    index_name: str, schema: str | None = None, concurrently: bool = True
) -> str:
    """Drop an index by name."""
    return await performance.drop_index(index_name, schema=schema, concurrently=concurrently)


@mcp.tool()
async def vacuum_analyze(table: str | None = None, schema: str | None = None) -> str:
    """Run VACUUM ANALYZE on a table or the whole database."""
    return await performance.vacuum_analyze(table=table, schema=schema)


@mcp.tool()
async def get_connections(limit: int = 50) -> str:
    """List active PostgreSQL backends/connections."""
    return await admin.get_connections(limit=limit)


@mcp.tool()
async def kill_query(pid: int, terminate: bool = False) -> str:
    """Cancel a running query by pid. Set terminate=true to hard-kill the backend."""
    return await admin.kill_query(pid, terminate=terminate)


@mcp.tool()
async def get_locks(granted: bool | None = None, limit: int = 100) -> str:
    """Show lock activity. Pass granted=false to see waiting locks only."""
    return await admin.get_locks(granted=granted, limit=limit)


@mcp.tool()
async def check_health() -> str:
    """Database health snapshot: version, size, connections, cache hit ratio."""
    return await admin.check_health()


@mcp.tool()
async def get_replication_status() -> str:
    """Show replication slots and lag statistics when available."""
    return await admin.get_replication_status()


@mcp.tool()
async def apply_migration(name: str, sql: str, rollback_sql: str | None = None) -> str:
    """Apply a named SQL migration and record it in pgchat_migrations."""
    return await migration.apply_migration(name, sql, rollback_sql=rollback_sql)


@mcp.tool()
async def rollback_migration(
    migration_id: int | None = None, name: str | None = None
) -> str:
    """Rollback a migration using its stored rollback_sql (latest if unspecified)."""
    return await migration.rollback_migration(migration_id=migration_id, name=name)


@mcp.tool()
async def list_migrations(limit: int = 50) -> str:
    """List applied/rolled-back migrations tracked by pgchat."""
    return await migration.list_migrations(limit=limit)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
