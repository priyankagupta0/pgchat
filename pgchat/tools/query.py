from __future__ import annotations

from typing import Any

from pgchat.db import pool
from pgchat.safety.classify import classify_sql
from pgchat.tools.format import dumps, rows_to_dicts


async def run_query(sql: str, limit: int | None = None) -> str:
    """Execute a PostgreSQL statement. SELECT results are returned as JSON rows."""
    cfg = pool.get_config()
    classification = classify_sql(sql, block_drop_database=cfg.safety.block_drop_database)
    if classification.blocked:
        return dumps({"error": classification.reason, "risk": classification.risk})

    max_rows = limit or cfg.safety.max_rows
    db = await pool.get_pool()
    async with db.acquire() as conn:
        # Read path: fetch rows
        if classification.risk == "read" and sql.strip().upper().startswith(
            ("SELECT", "WITH", "SHOW", "VALUES", "EXPLAIN")
        ):
            # Cap rows for plain SELECT (not EXPLAIN)
            upper = sql.strip().upper()
            fetch_sql = sql
            if upper.startswith(("SELECT", "WITH")) and "LIMIT" not in upper:
                fetch_sql = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS _pgchat_q LIMIT {max_rows}"
            rows = await conn.fetch(fetch_sql)
            return dumps(
                {
                    "risk": classification.risk,
                    "row_count": len(rows),
                    "rows": rows_to_dicts(rows),
                    "truncated": len(rows) >= max_rows,
                }
            )

        status = await conn.execute(sql)
        return dumps({"risk": classification.risk, "status": status})


async def explain_query(sql: str, analyze: bool = False) -> str:
    """Run EXPLAIN (optionally ANALYZE) on a SQL statement."""
    prefix = "EXPLAIN (ANALYZE true, BUFFERS true, FORMAT JSON)" if analyze else "EXPLAIN (FORMAT JSON)"
    wrapped = f"{prefix} {sql.rstrip().rstrip(';')}"
    db = await pool.get_pool()
    async with db.acquire() as conn:
        rows = await conn.fetch(wrapped)
        plans: list[Any] = []
        for r in rows:
            val = list(r.values())[0]
            plans.append(val)
        return dumps({"explain": plans, "analyze": analyze})
