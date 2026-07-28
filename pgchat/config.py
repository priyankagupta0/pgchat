from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import toml
from pydantic import BaseModel, Field, field_validator

CONFIG_DIR = Path.home() / ".pgchat"
CONFIG_FILE = CONFIG_DIR / "config.toml"
AUDIT_DIR = CONFIG_DIR / "audit"
SCHEMA_CACHE_DIR = CONFIG_DIR / "schema_cache"


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "postgres"
    min_pool_size: int = 1
    max_pool_size: int = 5
    statement_timeout_ms: int = 30_000

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class GeminiConfig(BaseModel):
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.1
    max_tool_rounds: int = 12

    @field_validator("api_key", mode="before")
    @classmethod
    def env_fallback(cls, v: str) -> str:
        return v or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")


class SafetyConfig(BaseModel):
    require_approval_for: list[str] = Field(
        default_factory=lambda: ["write", "ddl", "destructive", "admin"]
    )
    auto_approve_read: bool = True
    block_drop_database: bool = True
    max_rows: int = 500
    audit_enabled: bool = True


class Config(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    default_schema: str = "public"


def load_config(path: Path | None = None) -> Config:
    config_path = path or CONFIG_FILE
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found at {config_path}. Run 'pgchat init' to set up."
        )
    with open(config_path, encoding="utf-8") as f:
        data = toml.load(f)
    return Config.model_validate(data)


def save_config(config: Config, path: Path | None = None) -> Path:
    config_path = path or CONFIG_FILE
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        toml.dump(config.model_dump(), f)
    return config_path


RiskLevel = Literal["read", "write", "ddl", "destructive", "admin"]
