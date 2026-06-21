import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

EMBEDDING_DIM_DEFAULT = 1536


def get_embedding_dim() -> int:
    """Single source of truth for the pgvector embedding dimension.

    Read from the EMBEDDING_DIM env var (default 1536). Intentionally uses
    os.getenv rather than Settings so model/migration imports don't require
    DATABASE_URL. Must be set as a real environment variable at BOTH app-run
    and `alembic upgrade` time for the schema to match the app.
    """
    return int(os.getenv("EMBEDDING_DIM", str(EMBEDDING_DIM_DEFAULT)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    embedding_dim: int = EMBEDDING_DIM_DEFAULT


@lru_cache
def get_settings() -> Settings:
    return Settings()
