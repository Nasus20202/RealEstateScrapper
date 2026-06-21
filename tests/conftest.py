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
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        raw = pg.get_connection_url()  # postgresql+psycopg2://...
        yield raw.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url):
    eng = create_engine(pg_url)
    yield eng
    await eng.dispose()
