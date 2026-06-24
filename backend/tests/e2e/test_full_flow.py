# tests/e2e/test_full_flow.py
import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import (
    get_event_bus_dep,
    get_fetcher_dep,
    get_geocoder_dep,
    get_llm_client_dep,
    get_session,
    get_session_factory,
)
from realestate.db.engine import create_session_factory
from realestate.events.bus import EventBus
from realestate.models import Base
from tests.fixtures.loader import load_fixture


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
    base._REGISTRY.clear()
    base._REGISTRY.update({"otodom": saved["otodom"]})
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    app.dependency_overrides[get_geocoder_dep] = lambda: None
    app.dependency_overrides[get_event_bus_dep] = lambda: EventBus()
    app.dependency_overrides[get_llm_client_dep] = lambda: None  # rule-based degradation
    return app


async def test_full_flow_scrape_list_detail_favorite(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # 1) scrape
        scraped = await client.post(
            "/scrape", json={"city": "gdansk", "source_ids": ["otodom"], "max_pages": 2}
        )
        assert scraped.status_code == 200
        assert scraped.json()["runs"][0]["status"] == "success"
        assert scraped.json()["runs"][0]["new_count"] >= 20

        # 2) list (rule-based ranking, no LLM)
        listed = await client.get("/listings", params={"limit": 100})
        body = listed.json()
        assert body["total"] >= 20
        first_id = body["items"][0]["id"]

        # 3) details
        detail = await client.get(f"/listings/{first_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == first_id

        # 4) ulubione
        fav = await client.post("/favorites", json={"listing_id": first_id})
        assert fav.status_code == 201
        favs = await client.get("/favorites")
        assert any(f["listing_id"] == first_id for f in favs.json())
