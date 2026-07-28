from __future__ import annotations

import re
from dataclasses import dataclass

from pgchat.config import RiskLevel

_READ_START = re.compile(
    r"^\s*(WITH\b[\s\S]+?\bSELECT\b|SELECT\b|SHOW\b|EXPLAIN\b|VALUES\b|TABLE\b)",
    re.IGNORECASE,
)
_DROP_DB = re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE)
_ADMIN = re.compile(
    r"\b(pg_cancel_backend|pg_terminate_backend|pg_reload_conf|pg_rotate_logfile)\b",
    re.IGNORECASE,
)
_DESTRUCTIVE = re.compile(
    r"\b(DROP\s+(SCHEMA|TABLE|INDEX|VIEW|MATERIALIZED\s+VIEW|FUNCTION|TYPE|ROLE|USER|EXTENSION|DATABASE)"
    r"|TRUNCATE\b|ALTER\s+SYSTEM\b)\b",
    re.IGNORECASE,
)
_DDL = re.compile(
    r"\b(CREATE|ALTER|DROP|REINDEX|CLUSTER|COMMENT\s+ON|GRANT|REVOKE|VACUUM|ANALYZE|REFRESH\s+MATERIALIZED)\b",
    re.IGNORECASE,
)
_WRITE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|COPY|CALL|DO\b|LOCK\b)\b",
    re.IGNORECASE,
)
_DELETE = re.compile(r"\bDELETE\s+FROM\s+[\w.\"]+", re.IGNORECASE)
_UPDATE = re.compile(r"\bUPDATE\s+[\w.\"]+\s+SET\b", re.IGNORECASE)


def _missing_where(sql: str) -> bool:
    delete = _DELETE.search(sql)
    if delete:
        rest = sql[delete.end() :].lstrip()
        if not rest.upper().startswith("WHERE"):
            return True
    update = _UPDATE.search(sql)
    if update:
        rest = sql[update.end() :]
        if not re.search(r"\bWHERE\b", rest, re.IGNORECASE):
            return True
    return False


@dataclass(frozen=True)
class Classification:
    risk: RiskLevel
    reason: str
    blocked: bool = False


def classify_sql(sql: str, *, block_drop_database: bool = True) -> Classification:
    text = sql.strip()
    if not text:
        return Classification("read", "empty SQL", blocked=True)

    if block_drop_database and _DROP_DB.search(text):
        return Classification(
            "destructive",
            "DROP DATABASE is blocked by policy",
            blocked=True,
        )

    if _ADMIN.search(text):
        return Classification("admin", "Admin / backend control function")

    if _DESTRUCTIVE.search(text) or _missing_where(text):
        return Classification("destructive", "Potentially destructive SQL")

    if _DDL.search(text):
        return Classification("ddl", "DDL / maintenance statement")

    if _WRITE.search(text):
        return Classification("write", "Data-modifying statement")

    if _READ_START.search(text):
        return Classification("read", "Read-only statement")

    return Classification("write", "Unrecognized statement — treating as write")


def classify_tool(tool_name: str) -> Classification:
    """Map MCP tool names to risk levels when SQL is not the primary input."""
    read_tools = {
        "run_query",
        "explain_query",
        "list_tables",
        "describe_table",
        "list_indexes",
        "suggest_indexes",
        "get_slow_queries",
        "get_connections",
        "get_table_stats",
        "get_locks",
        "check_health",
        "get_replication_status",
        "get_schema_cache",
        "refresh_schema_cache",
        "list_migrations",
    }
    write_tools = {"apply_migration", "create_index"}
    ddl_tools = {"vacuum_analyze", "drop_index"}
    destructive_tools = {"rollback_migration"}
    admin_tools = {"kill_query"}

    if tool_name in admin_tools:
        return Classification("admin", f"Admin tool: {tool_name}")
    if tool_name in destructive_tools:
        return Classification("destructive", f"Destructive tool: {tool_name}")
    if tool_name in ddl_tools:
        return Classification("ddl", f"DDL/maintenance tool: {tool_name}")
    if tool_name in write_tools:
        return Classification("write", f"Write tool: {tool_name}")
    if tool_name in read_tools:
        return Classification("read", f"Read tool: {tool_name}")
    return Classification("write", f"Unknown tool: {tool_name}")
