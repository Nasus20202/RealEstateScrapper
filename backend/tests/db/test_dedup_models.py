from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, DedupGroup, DedupMember, Listing
from realestate.models.enums import ListingStatus


async def _listing(s, ext) -> Listing:
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


async def test_dedup_group_with_members(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        g = DedupGroup(created_at=datetime.now(UTC))
        g.members = [DedupMember(listing_id=l1.id), DedupMember(listing_id=l2.id)]
        s.add(g)
        await s.flush()
        loaded = (await s.execute(select(DedupMember))).scalars().all()
        assert len(loaded) == 2


async def test_listing_in_one_group_only(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "c")
        g1 = DedupGroup(created_at=datetime.now(UTC))
        g1.members = [DedupMember(listing_id=l1.id)]
        s.add(g1)
        await s.flush()
        g2 = DedupGroup(created_at=datetime.now(UTC))
        g2.members = [DedupMember(listing_id=l1.id)]
        s.add(g2)
        with pytest.raises(IntegrityError):
            await s.flush()
