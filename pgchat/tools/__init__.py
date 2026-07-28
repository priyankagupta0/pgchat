from __future__ import annotations

from pgchat.tools import admin, migration, performance, query, schema

TOOL_HANDLERS = {
    "run_query": query.run_query,
    "explain_query": query.explain_query,
    "list_tables": schema.list_tables,
    "describe_table": schema.describe_table,
    "list_indexes": schema.list_indexes,
    "get_table_stats": schema.get_table_stats,
    "get_schema_cache": schema.get_schema_cache,
    "refresh_schema_cache": schema.refresh_schema_cache,
    "get_slow_queries": performance.get_slow_queries,
    "suggest_indexes": performance.suggest_indexes,
    "create_index": performance.create_index,
    "drop_index": performance.drop_index,
    "vacuum_analyze": performance.vacuum_analyze,
    "get_connections": admin.get_connections,
    "kill_query": admin.kill_query,
    "get_locks": admin.get_locks,
    "check_health": admin.check_health,
    "get_replication_status": admin.get_replication_status,
    "apply_migration": migration.apply_migration,
    "rollback_migration": migration.rollback_migration,
    "list_migrations": migration.list_migrations,
}

__all__ = ["TOOL_HANDLERS", "admin", "migration", "performance", "query", "schema"]
