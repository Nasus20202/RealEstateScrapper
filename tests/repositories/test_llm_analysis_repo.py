# tests/repositories/test_llm_analysis_repo.py
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing, LLMAnalysis
from realestate.models.enums import ListingStatus
from realestate.repositories.llm_analysis import LLMAnalysisRepository


async def _listing(s: AsyncSession) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id="y1", url="u", title="t",
                      raw_hash="hh", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_get_returns_none_then_row(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        repo = LLMAnalysisRepository(s)
        assert await repo.get(listing.id, "hh") is None
        await repo.add(LLMAnalysis(listing_id=listing.id, content_hash="hh",
                                   summary="x", features={}, model="m",
                                   created_at=datetime.now(UTC)))
        got = await repo.get(listing.id, "hh")
        assert got is not None and got.summary == "x"
