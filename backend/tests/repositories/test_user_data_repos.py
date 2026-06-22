from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing, SavedSearch
from realestate.models.enums import ListingStatus
from realestate.repositories.user_data import (
    AppSettingRepository,
    FavoriteRepository,
    SavedSearchRepository,
)


async def _listing(s, ext="a") -> Listing:
    now = datetime.now(UTC)
    listing = Listing(
        source_id="otodom",
        external_id=ext,
        url="u",
        title="t",
        raw_hash="h",
        status=ListingStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        images=[],
    )
    s.add(listing)
    await s.flush()
    return listing


async def test_saved_search_repo_crud(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        repo = SavedSearchRepository(s)
        created = await repo.add(
            SavedSearch(name="x", filters={}, nl_query=None, created_at=datetime.now(UTC))
        )
        assert await repo.get(created.id) is not None
        assert len(await repo.list_all()) == 1
        assert await repo.delete(created.id) is True
        assert await repo.get(created.id) is None


async def test_favorite_repo_idempotent_add_and_delete(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        repo = FavoriteRepository(s)
        await repo.add(listing.id)
        await repo.add(listing.id)  # idempotentne
        assert await repo.exists(listing.id) is True
        assert len(await repo.list_all()) == 1
        assert await repo.delete(listing.id) is True
        assert await repo.exists(listing.id) is False


async def test_app_setting_repo_upsert(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        repo = AppSettingRepository(s)
        assert await repo.get("k") is None
        await repo.set("k", {"v": 1})
        await repo.set("k", {"v": 2})  # upsert
        assert await repo.get("k") == {"v": 2}
        assert (await repo.all())["k"] == {"v": 2}
