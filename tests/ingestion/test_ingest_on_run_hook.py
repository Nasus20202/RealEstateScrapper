# tests/ingestion/test_ingest_on_run_hook.py
import pytest

from realestate.db.engine import create_session_factory
from realestate.ingestion.service import IngestionService
from realestate.models import Base
from realestate.scrapers.base import SearchCriteria
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True

    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        empty_json = '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
        tag = f'<script id="__NEXT_DATA__" type="application/json">{empty_json}</script>'
        return f"<html>{tag}</html>"


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


async def test_on_run_called_per_source(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())

    seen = []

    async def on_run(run):
        seen.append((run.source_id, run.status.value, run.new_count))

    runs = await svc.ingest(
        SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=2, on_run=on_run
    )
    assert len(runs) == 1
    assert len(seen) == 1
    assert seen[0][0] == "otodom"
    assert seen[0][1] == "success"


async def test_on_run_exception_does_not_break_ingest(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())

    async def boom(run):
        raise RuntimeError("hook failed")

    runs = await svc.ingest(
        SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=2, on_run=boom
    )
    assert len(runs) == 1  # ingestia ukończona mimo wyjątku w hooku
