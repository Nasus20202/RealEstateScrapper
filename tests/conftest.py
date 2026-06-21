import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from realestate.config import get_settings
from realestate.db.engine import create_engine


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def pg_url() -> str:
    with PostgresContainer("pgvector/pgvector:pg18") as pg:
        raw = pg.get_connection_url()  # postgresql+psycopg2://...
        yield raw.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url):
    from sqlalchemy import text

    from realestate.models import Base

    eng = create_engine(pg_url)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS markettype CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS listingstatus CASCADE"))
    await eng.dispose()
