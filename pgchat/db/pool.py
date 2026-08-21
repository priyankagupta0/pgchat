from __future__ import annotations

import asyncpg

from pgchat.config import Config

_pool: asyncpg.Pool | None = None
_config: Config | None = None


async def init_pool(config: Config) -> asyncpg.Pool:
    global _pool, _config
    if _pool is not None:
        return _pool

    _config = config
    db = config.database
    _pool = await asyncpg.create_pool(
        host=db.host,
        port=db.port,
        user=db.user,
        password=db.password,
        database=db.database,
        min_size=db.min_pool_size,
        max_size=db.max_pool_size,
        command_timeout=db.statement_timeout_ms / 1000.0,
        server_settings={
            "statement_timeout": str(db.statement_timeout_ms),
            "application_name": "pgchat",
        },
    )
    return _pool


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def close_pool() -> None:
    global _pool, _config
    if _pool is not None:
        await _pool.close()
        _pool = None
        _config = None


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config not loaded. Call init_pool() first.")
    return _config
