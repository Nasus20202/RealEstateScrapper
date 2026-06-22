from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.config import get_embedding_dim
from realestate.enrichment.service import EnrichmentService
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, Listing, LLMAnalysis
from realestate.models.enums import ListingStatus


class _SpyClient:
    """Liczy wywołania; zwraca stały JSON i deterministyczny embedding."""

    def __init__(self):
        self.complete_calls = 0
        self.embed_calls = 0

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        self.complete_calls += 1
        return LLMResult(content='{"summary": "ok", "features": {"balkon": true}}')

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        dim = get_embedding_dim()
        return [[0.1] * dim for _ in texts]


class _NonDictClient:
    """Spy client whose complete() returns valid-but-non-dict JSON."""

    def __init__(self):
        self.complete_calls = 0
        self.embed_calls = 0

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        self.complete_calls += 1
        return LLMResult(content="[1, 2, 3]")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        dim = get_embedding_dim()
        return [[0.1] * dim for _ in texts]


async def _listing(s: AsyncSession, *, raw_hash="h1") -> Listing:
    now = datetime.now(UTC)
    listing = Listing(
        source_id="otodom",
        external_id="e1",
        url="u",
        title="Mieszkanie",
        description="ladne",
        city="Gdansk",
        district="Wrzeszcz",
        rooms=3,
        area_m2=60.0,
        raw_hash=raw_hash,
        status=ListingStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        images=[],
    )
    s.add(listing)
    await s.flush()
    return listing


async def test_enrich_creates_analysis_and_sets_embedding(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        client = _SpyClient()
        svc = EnrichmentService(s, client, model_name="test-model")
        did = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did is True
        assert client.complete_calls == 1 and client.embed_calls == 1
        row = (await s.execute(select(LLMAnalysis))).scalar_one()
        assert row.summary == "ok"
        assert row.features == {"balkon": True}
        assert listing.embedding is not None
        assert len(listing.embedding) == get_embedding_dim()


async def test_enrich_is_cached_on_second_call(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        client = _SpyClient()
        svc = EnrichmentService(s, client, model_name="test-model")
        await svc.enrich_listing(listing, now=datetime.now(UTC))
        did2 = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did2 is False
        assert client.complete_calls == 1  # bez ponownego wywołania
        count = (await s.execute(select(func.count()).select_from(LLMAnalysis))).scalar_one()
        assert count == 1


async def test_enrich_is_noop_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        svc = EnrichmentService(s, None)
        did = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did is False
        count = (await s.execute(select(func.count()).select_from(LLMAnalysis))).scalar_one()
        assert count == 0


async def test_enrich_graceful_fallback_for_non_dict_json(engine):
    """When the LLM returns valid JSON that is not an object, enrich_listing
    should return True (success) and persist empty summary/features."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s, raw_hash="h2")
        client = _NonDictClient()
        svc = EnrichmentService(s, client, model_name="test-model")
        did = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did is True
        row = (await s.execute(select(LLMAnalysis))).scalar_one()
        assert row.summary == ""
        assert row.features == {}
        assert listing.embedding is not None
        assert len(listing.embedding) == get_embedding_dim()
