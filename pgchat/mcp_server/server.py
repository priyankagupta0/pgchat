"""MCP server for natural language Postgres database interactions."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from pgchat.config import Settings
from pgchat.db.pool import Database
from pgchat.logging_config import get_logger, setup_logging
from pgchat.tools.query import QueryResult, run_query

logger = get_logger(__name__)

# FastMCP server instance
mcp = FastMCP("PgChat")


def _serialize_query_result(result: QueryResult) -> dict[str, Any]:
    """
    Serialize QueryResult Pydantic model to JSON-compatible dict.

    Args:
        result: QueryResult model from query execution.

    Returns:
        Dictionary representation suitable for MCP transport.
    """
    return result.model_dump(mode="json")


@mcp.tool()
async def run_query_tool(sql: str, limit: int = 100) -> dict[str, Any]:
    """
    Execute a read-only SQL query against Postgres.

    This tool supports only read-only operations for safety:
    - SELECT queries with optional JOINs, CTEs, subqueries
    - WITH (Common Table Expressions)
    - SHOW statements for configuration inspection
    - EXPLAIN for query analysis
    - VALUES for inline data
    - DESCRIBE for schema inspection

    Write operations are blocked at both application and database levels.

    Args:
        sql: Read-only SQL query to execute.
        limit: Maximum number of rows to return (default: 100, max: 1000).

    Returns:
        Dictionary containing:
        - columns: List of column names
        - rows: List of row dictionaries
        - row_count: Number of rows returned
        - duration_ms: Query execution time in milliseconds
        - truncated: Whether results were truncated due to limit
        - error: Error information if query failed (optional)

    Examples:
        >>> await run_query_tool("SELECT * FROM users LIMIT 5")
        >>> await run_query_tool("SHOW server_version")
        >>> await run_query_tool("EXPLAIN SELECT * FROM large_table", limit=10)
    """
    try:
        result = await run_query(sql=sql, limit=limit)
        return _serialize_query_result(result)
    except Exception as e:
        logger.exception("Unexpected error in run_query_tool")
        # Return error in QueryResult format
        error_result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            duration_ms=0.0,
            truncated=False,
            error={
                "code": "TOOL_ERROR",
                "message": f"Tool execution failed: {str(e)}",
            },
        )
        return _serialize_query_result(error_result)


async def _setup_and_run(settings: Settings) -> None:
    """
    Initialize database pool and run the MCP server.

    Args:
        settings: Application settings containing database configuration.

    Note:
        FastMCP handles stdio transport by default. The server communicates
        with MCP clients via stdin/stdout following the MCP protocol.
    """
    logger.info("Initializing PgChat MCP server...")

    try:
        await Database.init(settings)
        logger.info("Database pool initialized successfully")

        logger.info("Starting MCP server (stdio transport)")
        await mcp.run_async()

    except Exception:
        logger.exception("Failed to start MCP server")
        raise
    finally:
        logger.info("Shutting down database pool...")
        await Database.close()
        logger.info("Database pool closed")


def main() -> None:
    """
    Main entry point for the MCP server.

    Loads configuration, sets up logging, initializes the database pool,
    and starts the MCP server with stdio transport.

    Raises:
        RuntimeError: If configuration is missing or invalid.
        Exception: If server startup fails.
    """
    # Setup logging for MCP server
    setup_logging(console_level="INFO", enable_file=True)

    try:
        settings = Settings.load()
        logger.info(f"Settings loaded. Database: {settings.database_url}")
    except Exception:
        logger.exception("Failed to load settings")
        logger.error("Ensure PGCHAT_GEMINI_API_KEY and PGCHAT_DATABASE_URL are set")
        raise

    try:
        asyncio.run(_setup_and_run(settings))
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception:
        logger.exception("Server crashed")
        raise


if __name__ == "__main__":
    main()