import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_fetcher_dep, get_session, get_session_factory
from realestate.db.engine import create_session_factory
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
    keep = {"otodom": base._REGISTRY["otodom"]}
    base._REGISTRY.clear()
    base._REGISTRY.update(keep)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def _create_schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    return app


async def test_scrape_then_list_runs(engine):
    await _create_schema(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/scrape", json={"city": "gdansk", "source_ids": ["otodom"], "max_pages": 2}
        )
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["new_count"] >= 20
        run_id = runs[0]["id"]

        listed = await client.get("/scrape/runs")
        assert listed.status_code == 200
        assert any(r["id"] == run_id for r in listed.json())

        one = await client.get(f"/scrape/runs/{run_id}")
        assert one.status_code == 200 and one.json()["id"] == run_id

        missing = await client.get("/scrape/runs/999999")
        assert missing.status_code == 404
