import asyncio
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.repositories.listings import ListingRepository


def _alembic_config() -> Config:
    return Config("alembic.ini")


async def upgrade_to_head(pg_url: str, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from realestate.config import get_settings

    get_settings.cache_clear()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, command.upgrade, _alembic_config(), "head")


async def test_pgvector_extension_enabled(engine, pg_url, monkeypatch):
    await upgrade_to_head(pg_url, monkeypatch)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        assert result.scalar_one_or_none() == 1


async def test_postgis_migration_adds_geometry_support(engine, pg_url, monkeypatch):
    await upgrade_to_head(pg_url, monkeypatch)
    async with engine.connect() as conn:
        extension = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'"))
        assert extension.scalar_one_or_none() == 1

        geom_column = await conn.execute(
            text(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_name = 'listings' AND column_name = 'geom'
                """
            )
        )
        assert geom_column.scalar_one() == "geometry"

        geom = await conn.execute(
            text("SELECT ST_AsText(ST_SetSRID(ST_MakePoint(18.6466, 54.3520), 4326))")
        )
        assert geom.scalar_one() == "POINT(18.6466 54.352)"


async def test_orm_enum_binding_matches_migrated_schema(engine, pg_url, monkeypatch):
    """Regression: against a MIGRATION-built schema (not create_all), inserting and
    filtering by an enum must work. Previously the ORM bound the member NAME ('ACTIVE')
    while the migration created lowercase enum labels ('active'), causing a runtime
    InvalidTextRepresentationError that create_all-based tests never caught.
    """
    await upgrade_to_head(pg_url, monkeypatch)

    now = datetime.now(UTC)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(
            Listing(
                source_id="otodom",
                external_id="m1",
                url="u",
                title="t",
                raw_hash="h",
                status=ListingStatus.ACTIVE,
                first_seen=now,
                last_seen=now,
                images=[],
            )
        )
        await session.commit()
        # Filtering by the enum exercises the bind that broke against the migrated enum.
        assert await ListingRepository(session).count_active() == 1
