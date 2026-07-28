from typing import Tuple, Type
from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource
from pathlib import Path

CONFIG_DIR = Path.home() / ".pgchat"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class Settings(BaseSettings):
    gemini_api_key: str
    database_url: PostgresDsn
    gemini_model: str = "gemini-3-flash"
    query_limit: int = Field(
        default=100, description="Max number of rows to return for a query", gt=0
    )
    statement_timeout_ms: int = Field(
        default=10_000,
        description="Statement timeout in milliseconds for queries",
        gt=0,
    )
    pool_min_size: int = Field(
        ge=0,
        default=1,
        description="Minimum number of connections in the database pool",
    )
    pool_max_size: int = Field(
        ge=1,
        default=10,
        description="Maximum number of connections in the database pool",
    )

    model_config = SettingsConfigDict(
        env_prefix="PGCHAT_",
        toml_file=CONFIG_FILE,
        extra="ignore",
        frozen=True,
    )

    @model_validator(mode="after")
    def validate_pool_sizes(self) -> "Settings":
        if self.pool_min_size > self.pool_max_size:
            raise ValueError("pool_min_size cannot be greater than pool_max_size")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )

    @classmethod
    def load(cls) -> "Settings":
        """Explicit constructor for readability"""
        return cls()


def write_default_config() -> None:
    """Writes a default config file to the user's home directory."""

    CONFIG_DIR.mkdir(exist_ok=True)

    if CONFIG_FILE.exists():
        return

    CONFIG_FILE.write_text(
        """# PGChat local config

        # Get this from Google AI Studio
        gemini_api_key = "PASTE_GEMINI_API_KEY_HERE"

        # Local or remote Postgres connection string
        database_url = "postgresql://postgres:postgres@localhost:5432/postgres"

        # Gemini model
        gemini_model = "gemini-2.5-flash"

        # Default max rows returned to the LLM
        query_limit = 100

        # Safety timeout for statements
        statement_timeout_ms = 10000

        # Connection pool sizing
        pool_min_size = 1
        pool_max_size = 5
        """,
        encoding="utf-8",
    )

write_default_config()
settings = Settings.load()