# tests/db/test_llm_analysis_model.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing, LLMAnalysis
from realestate.models.enums import ListingStatus


async def _make_listing(session: AsyncSession) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(
        source_id="otodom", external_id="x1", url="http://x", title="t",
        raw_hash="h1", status=ListingStatus.ACTIVE, first_seen=now, last_seen=now,
        images=[],
    )
    session.add(listing)
    await session.flush()
    return listing


async def test_llm_analysis_persists(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _make_listing(s)
        s.add(LLMAnalysis(
            listing_id=listing.id, content_hash="h1", summary="streszczenie",
            features={"balkon": True}, model="m", created_at=datetime.now(UTC),
        ))
        await s.flush()
        row = (await s.execute(select(LLMAnalysis))).scalar_one()
        assert row.features == {"balkon": True}
        assert row.summary == "streszczenie"


async def test_llm_analysis_unique_listing_hash(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _make_listing(s)
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="a",
                          features={}, model="m", created_at=datetime.now(UTC)))
        await s.flush()
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="b",
                          features={}, model="m", created_at=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            await s.flush()
