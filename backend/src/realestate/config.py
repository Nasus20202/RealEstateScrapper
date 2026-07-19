import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

EMBEDDING_DIM_DEFAULT = 2048
DEFAULT_CITIES = ["Gdańsk", "Gdynia", "Sopot"]


def get_embedding_dim() -> int:
    """Single source of truth for the pgvector embedding dimension.

    Read from the EMBEDDING_DIM env var or local .env file (default 2048).
    Intentionally avoids Settings so model/migration imports don't require
    DATABASE_URL. Must be the same at BOTH app-run and `alembic upgrade` time
    for the schema to match the app.
    """
    env_value = os.getenv("EMBEDDING_DIM")
    if env_value is not None:
        return int(env_value)

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "EMBEDDING_DIM":
                return int(value.strip().strip("\"'"))

    return EMBEDDING_DIM_DEFAULT


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


def get_api_root_path() -> str:
    """Public path prefix used when the API is served behind a stripping proxy."""
    raw = os.getenv("API_ROOT_PATH", "").strip()
    if raw and not raw.startswith("/"):
        return f"/{raw}"
    return raw.rstrip("/")


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
    # --- Fetcher retry / backoff (transient block & error recovery) ---
    scraper_max_retries: int = 10
    scraper_backoff_base_seconds: float = 1.0
    scraper_backoff_max_seconds: float = 300.0
    structured_logging: bool = True

    # --- LLM (konfigurowalny dostawca, OpenAI-compatible). Nic nie hardcodowane. ---
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_embedding_model: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    scheduler_enabled: bool = False
    scheduler_default_interval_minutes: int = 360
    scheduler_cron: str | None = None
    scraper_default_cities: list[str] = DEFAULT_CITIES
    db_migrate_on_startup: bool = True

    # --- Geocoding (OpenStreetMap/Nominatim by default; nothing hardcoded). ---
    # Scraped listing data has no coordinates, so addresses are geocoded at
    # ingestion to fill listings.lat/lon for the map. Disable to skip map pins.
    geocoding_enabled: bool = True
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "RealEstateScrapper/1.0 (local tool)"
    geocoding_min_delay_seconds: float = 1.0
    geocoding_timeout_seconds: float = 10.0

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_model and self.llm_embedding_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
