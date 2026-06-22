from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import AppSetting, Base, Favorite, Listing, SavedSearch
from realestate.models.enums import ListingStatus


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


async def test_saved_search_and_app_setting_persist(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add(
            SavedSearch(
                name="tanie 2pok",
                filters={"max_price": 500000, "min_rooms": 2},
                nl_query="blisko morza",
                created_at=datetime.now(UTC),
            )
        )
        s.add(AppSetting(key="scheduler_interval_minutes", value={"v": 60}))
        await s.flush()
        ss = (await s.execute(select(SavedSearch))).scalar_one()
        assert ss.filters["max_price"] == 500000
        setting = (await s.execute(select(AppSetting))).scalar_one()
        assert setting.value == {"v": 60}


async def test_favorite_unique(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        s.add(Favorite(listing_id=listing.id, created_at=datetime.now(UTC)))
        await s.flush()
        s.add(Favorite(listing_id=listing.id, created_at=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            await s.flush()
