from __future__ import annotations

from pgchat.db import pool
from pgchat.tools.format import dumps, rows_to_dicts


async def get_connections(limit: int = 50) -> str:
    """List active database connections / backends."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              pid,
              usename,
              application_name,
              client_addr::text AS client_addr,
              state,
              wait_event_type,
              wait_event,
              LEFT(query, 200) AS query,
              EXTRACT(EPOCH FROM (now() - query_start))::int AS query_age_sec
            FROM pg_stat_activity
            WHERE pid <> pg_backend_pid()
            ORDER BY query_start NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    return dumps({"connections": rows_to_dicts(rows)})


async def kill_query(pid: int, terminate: bool = False) -> str:
    """Cancel (or terminate) a backend by pid."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        if terminate:
            ok = await conn.fetchval("SELECT pg_terminate_backend($1)", pid)
            action = "terminate"
        else:
            ok = await conn.fetchval("SELECT pg_cancel_backend($1)", pid)
            action = "cancel"
    return dumps({"action": action, "pid": pid, "success": bool(ok)})


async def get_locks(granted: bool | None = None, limit: int = 100) -> str:
    """Show current locks, optionally filtering by granted status."""
    db = await pool.get_pool()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              l.locktype,
              l.mode,
              l.granted,
              l.pid,
              a.usename,
              a.state,
              LEFT(a.query, 200) AS query,
              c.relname AS relation
            FROM pg_locks l
            LEFT JOIN pg_stat_activity a ON a.pid = l.pid
            LEFT JOIN pg_class c ON c.oid = l.relation
            WHERE ($1::boolean IS NULL OR l.granted = $1)
            ORDER BY l.granted, l.pid
            LIMIT $2
            """,
            granted,
            limit,
        )
    return dumps({"locks": rows_to_dicts(rows)})


async def check_health() -> str:
    """Quick database health snapshot: connectivity, size, connections, cache hit."""
    cfg = pool.get_config()
    pool_obj = await pool.get_pool()
    async with pool_obj.acquire() as conn:
        version = await conn.fetchval("SHOW server_version")
        size = await conn.fetchval("SELECT pg_size_pretty(pg_database_size(current_database()))")
        conns = await conn.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE state = 'active') AS active,
              COUNT(*) FILTER (WHERE state = 'idle') AS idle,
              COUNT(*) AS total,
              (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections
            FROM pg_stat_activity
            """
        )
        cache = await conn.fetchrow(
            """
            SELECT
              CASE WHEN blks_hit + blks_read = 0 THEN 100.0
                   ELSE round(100.0 * blks_hit / (blks_hit + blks_read), 2)
              END AS cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database()
            """
        )
        longest = await conn.fetchrow(
            """
            SELECT pid, LEFT(query, 120) AS query,
                   EXTRACT(EPOCH FROM (now() - query_start))::int AS age_sec
            FROM pg_stat_activity
            WHERE state = 'active' AND pid <> pg_backend_pid()
            ORDER BY query_start
            LIMIT 1
            """
        )
    return dumps(
        {
            "database": cfg.database.database,
            "version": version,
            "size": size,
            "connections": dict(conns) if conns else {},
            "cache_hit_ratio": float(cache["cache_hit_ratio"]) if cache else None,
            "longest_active_query": dict(longest) if longest else None,
            "status": "healthy",
        }
    )


async def get_replication_status() -> str:
    """Show replication / WAL status when available."""
    pool_obj = await pool.get_pool()
    async with pool_obj.acquire() as conn:
        is_replica = await conn.fetchval("SELECT pg_is_in_recovery()")
        slots = await conn.fetch(
            """
            SELECT slot_name, slot_type, active, restart_lsn::text AS restart_lsn
            FROM pg_replication_slots
            """
        )
        try:
            stats = await conn.fetch(
                """
                SELECT
                  client_addr::text AS client_addr,
                  state,
                  sync_state,
                  write_lag::text AS write_lag,
                  flush_lag::text AS flush_lag,
                  replay_lag::text AS replay_lag
                FROM pg_stat_replication
                """
            )
        except Exception as exc:  # noqa: BLE001
            stats = []
            err = str(exc)
        else:
            err = None
    return dumps(
        {
            "in_recovery": bool(is_replica),
            "replication_slots": rows_to_dicts(slots),
            "stat_replication": rows_to_dicts(stats),
            "error": err,
        }
    )
