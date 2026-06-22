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


async def test_pgvector_extension_enabled(engine, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from realestate.config import get_settings

    get_settings.cache_clear()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, command.upgrade, _alembic_config(), "head")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        assert result.scalar_one_or_none() == 1


async def test_orm_enum_binding_matches_migrated_schema(engine, pg_url, monkeypatch):
    """Regression: against a MIGRATION-built schema (not create_all), inserting and
    filtering by an enum must work. Previously the ORM bound the member NAME ('ACTIVE')
    while the migration created lowercase enum labels ('active'), causing a runtime
    InvalidTextRepresentationError that create_all-based tests never caught.
    """
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from realestate.config import get_settings

    get_settings.cache_clear()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, command.upgrade, _alembic_config(), "head")

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
