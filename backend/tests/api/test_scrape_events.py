import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_event_bus_dep, get_fetcher_dep, get_session_factory
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


async def test_scrape_publishes_events(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app()
    factory = create_session_factory(engine)
    bus = EventBus()
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    app.dependency_overrides[get_event_bus_dep] = lambda: bus

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with bus.subscribe() as queue:
            resp = await client.post(
                "/scrape",
                json={"city": "gdansk", "source_ids": ["otodom"], "max_pages": 2},
            )
            assert resp.status_code == 200
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            event = next(event for event in events if event["type"] == "scrape")
    assert any(event["type"] == "scrape_log" for event in events)
    assert event["type"] == "scrape"
    assert event["source_id"] == "otodom"
    assert event["status"] == "success"
    assert event["new"] >= 20
