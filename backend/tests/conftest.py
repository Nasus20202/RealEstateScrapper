import docker
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
    # Self-hosted runners keep Docker state between runs, and testcontainers'
    # DockerImage build (delete-then-tag) is racy on this daemon: it keeps
    # hitting "AlreadyExists: image ... already exists". Build the test DB
    # image directly with the docker SDK (no cache, force-remove) so we fully
    # control the build, then run PostgresContainer against it.
    client = docker.from_env()
    tag = "realestate-db:test"

    try:
        client.images.remove(tag, force=True)
    except docker.errors.ImageNotFound:
        pass
    try:
        client.images.prune(filters={"dangling": True})
    except docker.errors.APIError:
        pass

    client.images.build(
        path="..",
        dockerfile="docker/db/Dockerfile",
        tag=tag,
        nocache=True,
        rm=True,
        forcerm=True,
    )

    try:
        with PostgresContainer(tag) as pg:
            raw = pg.get_connection_url()  # postgresql+psycopg2://...
            yield raw.replace("postgresql+psycopg2", "postgresql+asyncpg")
    finally:
        try:
            client.images.remove(tag, force=True)
        except docker.errors.APIError:
            pass


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
