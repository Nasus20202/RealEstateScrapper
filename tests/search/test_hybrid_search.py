from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService


class _HybridClient:
    """embed zwraca wektor zależny od 'mark'; complete zwraca ranking faworyzujący id2."""

    def __init__(self, matches_json):
        self._matches = matches_json

    async def embed(self, texts):
        dim = get_embedding_dim()
        return [[1.0] + [0.0] * (dim - 1) for _ in texts]

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        return LLMResult(content=self._matches)


async def _listing(s, *, ext, vec):
    now = datetime.now(UTC)
    listing = Listing(
        source_id="otodom",
        external_id=ext,
        url="u",
        title=f"o {ext}",
        price=Decimal(400000),
        price_per_m2=Decimal(8000),
        area_m2=50.0,
        rooms=2,
        district="Wrzeszcz",
        city="Gdansk",
        raw_hash="h" + ext,
        status=ListingStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        images=[],
        embedding=vec,
    )
    s.add(listing)
    await s.flush()
    return listing


async def test_hybrid_degrades_to_rule_based_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        dim = get_embedding_dim()
        await _listing(s, ext="a", vec=[0.0] * dim)
        svc = SearchService(s, client=None)
        items, total = await svc.search_hybrid(ListingFilters(nl_query="cokolwiek"))
        assert total == 1 and items[0].score is None  # degradacja


async def test_hybrid_uses_llm_rerank(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        dim = get_embedding_dim()
        l1 = await _listing(s, ext="one", vec=[1.0] + [0.0] * (dim - 1))
        l2 = await _listing(s, ext="two", vec=[0.9] + [0.0] * (dim - 1))
        matches = (
            f'{{"matches": [{{"listing_id": {l2.id}, "score": 90, "reason": "blisko"}}, '
            f'{{"listing_id": {l1.id}, "score": 30, "reason": "dalej"}}]}}'
        )
        svc = SearchService(s, client=_HybridClient(matches))
        items, total = await svc.search_hybrid(ListingFilters(nl_query="blisko morza"))
        assert total == 2
        # ranking wg LLM: l2 (90) przed l1 (30)
        assert items[0].listing.id == l2.id and items[0].score == 90
        assert items[0].reason == "blisko"
        assert items[1].listing.id == l1.id
