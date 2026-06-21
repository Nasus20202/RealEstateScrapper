import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import text


def _alembic_config() -> Config:
    return Config("alembic.ini")


async def test_pgvector_extension_enabled(engine, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from realestate.config import get_settings
    get_settings.cache_clear()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, command.upgrade, _alembic_config(), "head")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        assert result.scalar_one_or_none() == 1
