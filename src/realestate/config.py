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


def get_cors_origins() -> list[str]:
    """Allowed CORS origins for the API, from the CORS_ALLOW_ORIGINS env var.

    Comma-separated list; default ``*`` (allow all — fine for a local tool).
    Read via os.getenv (not Settings) so ``create_app()`` does not require
    DATABASE_URL at construction time.
    """
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    embedding_dim: int = EMBEDDING_DIM_DEFAULT
    scraper_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    scraper_min_delay_seconds: float = 1.5
    scraper_nav_timeout_ms: int = 30000
    scraper_wait_until: str = "domcontentloaded"

    # --- LLM (konfigurowalny dostawca, OpenAI-compatible). Nic nie hardcodowane. ---
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_embedding_model: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    scheduler_enabled: bool = False
    scheduler_default_interval_minutes: int = 360

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_model and self.llm_embedding_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
