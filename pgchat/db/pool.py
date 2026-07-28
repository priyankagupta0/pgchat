"""Production-grade asyncpg connection pool manager."""

from __future__ import annotations

import asyncio
import asyncpg
from pgchat.config import Settings
from pgchat.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    """Production-grade asyncpg connection pool manager."""

    _pool: asyncpg.Pool | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def init(cls, settings: Settings) -> asyncpg.Pool:
        """Initialize the pool (idempotent). Call this once at startup."""
        async with cls._lock:
            if cls._pool is not None:
                logger.debug("Database pool already initialized, returning existing pool")
                return cls._pool

            if not settings.database_url:
                error_msg = "Missing database_url. Run `pgchat init` or set PGCHAT_DATABASE_URL."
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(f"Initializing database pool with min_size={settings.pool_min_size}, max_size={settings.pool_max_size}")

            try:
                cls._pool = await asyncpg.create_pool(
                    dsn=str(settings.database_url),
                    min_size=settings.pool_min_size,          # e.g. 5–10
                    max_size=settings.pool_max_size,          # e.g. 20–40
                    timeout=30.0,                             # Connection acquisition timeout
                    command_timeout=settings.statement_timeout_ms / 1000.0,  # Query execution timeout
                    
                    # Production hardening
                    max_queries=50000,                        # Recycle connections
                    max_inactive_connection_lifetime=300.0,   # 5 minutes
                    statement_cache_size=500,
                    
                    # Optional but recommended
                    # connection_class=YourCustomConnection,  # if you need custom codecs
                )
                logger.info("Database pool initialized successfully")
                return cls._pool

            except Exception as e:
                logger.exception(f"Failed to initialize database pool: {e}")
                raise

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """Get the active pool. Raises clear error if not initialized."""
        if cls._pool is None:
            error_msg = "Database pool not initialized. Call Database.init(settings) first."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        return cls._pool

    @classmethod
    async def close(cls) -> None:
        """Gracefully close the pool on shutdown."""
        async with cls._lock:
            if cls._pool is not None:
                logger.info("Closing database pool...")
                await cls._pool.close()
                cls._pool = None
                logger.info("Database pool closed successfully")
            else:
                logger.debug("Database pool already closed or never initialized")