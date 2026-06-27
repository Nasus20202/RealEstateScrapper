import asyncio
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import (
    get_event_bus_dep,
    get_fetcher_dep,
    get_llm_client_dep,
    get_session,
    get_session_factory,
)
from realestate.config import get_embedding_dim
from realestate.db.engine import create_session_factory
from realestate.events.bus import EventBus
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, Listing, LLMAnalysis
from realestate.models.enums import ListingStatus
from tests.fixtures.loader import load_fixture


class _EnrichmentClient:
    def __init__(self):
        self.complete_calls = 0
        self.embed_calls = 0

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        self.complete_calls += 1
        return LLMResult(content='{"summary": "ok", "features": {}}')

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        dim = get_embedding_dim()
        return [[0.5] * dim for _ in texts]


class _OneSourceFetcher:
    def __init__(self):
        self.first = True

    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        return (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
            "</script></html>"
        )


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401

    saved = dict(base._REGISTRY)
    keep = {"otodom": base._REGISTRY["otodom"]}
    base._REGISTRY.clear()
    base._REGISTRY.update(keep)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def _create_schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _app(engine, *, llm_client=None):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    app.dependency_overrides[get_event_bus_dep] = lambda: EventBus()
    app.dependency_overrides[get_llm_client_dep] = lambda: llm_client
    return app


async def _seed_listings_for_enrichment(engine):
    await _create_schema(engine)
    dim = get_embedding_dim()
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, tzinfo=UTC)
    t3 = datetime(2026, 1, 3, tzinfo=UTC)
    t4 = datetime(2026, 1, 4, tzinfo=UTC)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listings = [
            Listing(
                source_id="otodom",
                external_id="oldest",
                url="http://oldest",
                title="Oldest",
                city="Gdansk",
                raw_hash="h-oldest",
                status=ListingStatus.ACTIVE,
                first_seen=t1,
                last_seen=t1,
                images=[],
            ),
            Listing(
                source_id="otodom",
                external_id="middle",
                url="http://middle",
                title="Middle",
                city="Gdansk",
                raw_hash="h-middle",
                status=ListingStatus.ACTIVE,
                first_seen=t2,
                last_seen=t2,
                images=[],
            ),
            Listing(
                source_id="otodom",
                external_id="newest",
                url="http://newest",
                title="Newest",
                city="Gdansk",
                raw_hash="h-newest",
                status=ListingStatus.ACTIVE,
                first_seen=t3,
                last_seen=t3,
                images=[],
            ),
            Listing(
                source_id="otodom",
                external_id="done",
                url="http://done",
                title="Done",
                city="Gdansk",
                raw_hash="h-done",
                status=ListingStatus.ACTIVE,
                first_seen=t4,
                last_seen=t4,
                images=[],
                embedding=[0.1] * dim,
            ),
        ]
        s.add_all(listings)
        await s.flush()
        s.add(
            LLMAnalysis(
                listing_id=listings[3].id,
                content_hash="h-done",
                summary="done",
                features={},
                model="m",
                created_at=t4,
            )
        )
        await s.commit()


async def _fetch_embeddings(engine):
    async with AsyncSession(engine, expire_on_commit=False) as s:
        rows = (
            await s.execute(select(Listing.external_id, Listing.embedding).order_by(Listing.id))
        ).all()
        return {external_id: embedding for external_id, embedding in rows}


async def test_scrape_then_list_runs(engine):
    await _create_schema(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/scrape", json={"city": "gdansk", "source_ids": ["otodom"], "max_pages": 2}
        )
        assert resp.status_code == 204

        await asyncio.sleep(1)

        listed = await client.get("/scrape/runs")
        assert listed.status_code == 200
        runs = listed.json()
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["new_count"] >= 20
        run_id = runs[0]["id"]

        one = await client.get(f"/scrape/runs/{run_id}")
        assert one.status_code == 200 and one.json()["id"] == run_id

        missing = await client.get("/scrape/runs/999999")
        assert missing.status_code == 404


async def test_enrich_listings_uses_newest_pending_limit(engine):
    await _seed_listings_for_enrichment(engine)
    llm_client = _EnrichmentClient()
    app = _app(engine, llm_client=llm_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/scrape/enrich", json={"limit": 2})
    assert resp.status_code == 204

    await asyncio.sleep(1)

    embeddings = await _fetch_embeddings(engine)
    assert embeddings["oldest"] is None
    assert embeddings["middle"] is not None
    assert embeddings["newest"] is not None
    assert embeddings["done"] is not None
    assert llm_client.complete_calls == 2
    assert llm_client.embed_calls == 2


async def test_enrich_listings_all_pending_by_default(engine):
    await _seed_listings_for_enrichment(engine)
    llm_client = _EnrichmentClient()
    app = _app(engine, llm_client=llm_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/scrape/enrich", json={})
    assert resp.status_code == 204

    await asyncio.sleep(1)

    embeddings = await _fetch_embeddings(engine)
    assert all(embedding is not None for embedding in embeddings.values())
    assert llm_client.complete_calls == 3
    assert llm_client.embed_calls == 3


async def test_enrich_listings_requires_llm_client(engine):
    await _seed_listings_for_enrichment(engine)
    app = _app(engine, llm_client=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/scrape/enrich", json={"limit": 1})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "LLM client not configured"}
