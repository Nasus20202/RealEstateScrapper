import docker
import pytest
import pytest_asyncio
from testcontainers.core.image import DockerImage
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
    # On self-hosted runners, Docker state persists between CI runs and can end
    # up inconsistent (image "exists" but cannot be accessed: "No such image").
    # Remove all stale containers and every realestate-db image (incl. dangling
    # ones by ID), then prune dangling images/containers so the build starts
    # from a clean slate.
    client = docker.from_env()
    for container in client.containers.list(all=True, filters={"ancestor": "realestate-db:test"}):
        try:
            container.remove(force=True)
        except docker.errors.APIError:
            pass
    for image in client.images.list(filters={"reference": "realestate-db:*"}):
        try:
            client.images.remove(image.id, force=True)
        except docker.errors.APIError:
            pass
    try:
        client.images.prune(filters={"dangling": True})
        client.containers.prune()
    except docker.errors.APIError:
        pass

    with DockerImage(
        path="..",
        dockerfile_path="docker/db/Dockerfile",
        tag="realestate-db:test",
        clean_up=False,
    ):
        with PostgresContainer("realestate-db:test") as pg:
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
