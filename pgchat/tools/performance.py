from __future__ import annotations

from pgchat.db import pool
from pgchat.tools.format import dumps, rows_to_dicts


async def get_slow_queries(limit: int = 20, min_calls: int = 5) -> str:
    """Top queries by total time from pg_stat_statements (if installed)."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        installed = await conn.fetchval(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'"
        )
        if not installed:
            return dumps(
                {
                    "error": "pg_stat_statements extension is not installed",
                    "hint": "CREATE EXTENSION pg_stat_statements;",
                }
            )
        rows = await conn.fetch(
            """
            SELECT
              query,
              calls,
              round(total_exec_time::numeric, 2) AS total_ms,
              round(mean_exec_time::numeric, 2) AS mean_ms,
              rows
            FROM pg_stat_statements
            WHERE calls >= $1
            ORDER BY total_exec_time DESC
            LIMIT $2
            """,
            min_calls,
            limit,
        )
    return dumps({"slow_queries": rows_to_dicts(rows)})


async def suggest_indexes(table: str, schema: str | None = None) -> str:
    """Heuristic index suggestions from sequential scans and missing FK indexes."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    suggestions: list[dict] = []
    async with db.acquire() as conn:
        seq = await conn.fetchrow(
            """
            SELECT seq_scan, idx_scan, n_live_tup
            FROM pg_stat_user_tables
            WHERE schemaname = $1 AND relname = $2
            """,
            schema,
            table,
        )
        if seq and seq["seq_scan"] and seq["seq_scan"] > (seq["idx_scan"] or 0) * 2:
            suggestions.append(
                {
                    "type": "high_seq_scan",
                    "message": (
                        f"Table {schema}.{table} has high sequential scans "
                        f"({seq['seq_scan']}) vs index scans ({seq['idx_scan']}). "
                        "Review WHERE/JOIN columns for indexes."
                    ),
                    "stats": dict(seq),
                }
            )

        missing_fk = await conn.fetch(
            """
            SELECT
              c.conname AS constraint_name,
              a.attname AS column_name
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS u(attnum, ord) ON true
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = u.attnum
            WHERE c.contype = 'f'
              AND n.nspname = $1 AND t.relname = $2
              AND NOT EXISTS (
                SELECT 1
                FROM pg_index i
                WHERE i.indrelid = t.oid AND a.attnum = ANY (i.indkey)
              )
            """,
            schema,
            table,
        )
        for row in missing_fk:
            col = row["column_name"]
            suggestions.append(
                {
                    "type": "missing_fk_index",
                    "column": col,
                    "sql": f'CREATE INDEX ON "{schema}"."{table}" ("{col}");',
                    "message": f"Foreign key column {col} has no supporting index.",
                }
            )

        unused = await conn.fetch(
            """
            SELECT indexrelname AS index_name, idx_scan
            FROM pg_stat_user_indexes
            WHERE schemaname = $1 AND relname = $2 AND idx_scan = 0
            """,
            schema,
            table,
        )
        for row in unused:
            suggestions.append(
                {
                    "type": "unused_index",
                    "index": row["index_name"],
                    "message": f"Index {row['index_name']} has never been used (idx_scan=0).",
                }
            )

    return dumps({"schema": schema, "table": table, "suggestions": suggestions})


async def create_index(
    table: str,
    columns: str,
    schema: str | None = None,
    unique: bool = False,
    concurrently: bool = True,
    name: str | None = None,
) -> str:
    """Create an index on the given comma-separated columns."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    cols = [c.strip().strip('"') for c in columns.split(",") if c.strip()]
    if not cols:
        return dumps({"error": "No columns provided"})
    col_sql = ", ".join(f'"{c}"' for c in cols)
    idx_name = name or f"idx_{table}_{'_'.join(cols)}"[:60]
    uniq = "UNIQUE " if unique else ""
    conc = "CONCURRENTLY " if concurrently else ""
    sql = f'CREATE {uniq}INDEX {conc}"{idx_name}" ON "{schema}"."{table}" ({col_sql});'
    db = await pool.get_pool()
    # CONCURRENTLY cannot run inside a transaction block
    async with db.acquire() as conn:
        if concurrently:
            await conn.execute(sql)
        else:
            async with conn.transaction():
                await conn.execute(sql)
    return dumps({"status": "created", "index": idx_name, "sql": sql})


async def drop_index(index_name: str, schema: str | None = None, concurrently: bool = True) -> str:
    """Drop an index by name."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    conc = "CONCURRENTLY " if concurrently else ""
    sql = f'DROP INDEX {conc}IF EXISTS "{schema}"."{index_name}";'
    db = await pool.get_pool()
    async with db.acquire() as conn:
        await conn.execute(sql)
    return dumps({"status": "dropped", "index": index_name, "sql": sql})


async def vacuum_analyze(table: str | None = None, schema: str | None = None) -> str:
    """Run VACUUM ANALYZE on a table or the whole database."""
    cfg = pool.get_config()
    schema = schema or cfg.default_schema
    db = await pool.get_pool()
    async with db.acquire() as conn:
        # VACUUM cannot run inside a transaction
        if table:
            sql = f'VACUUM ANALYZE "{schema}"."{table}";'
        else:
            sql = "VACUUM ANALYZE;"
        await conn.execute(sql)
    return dumps({"status": "ok", "sql": sql})
