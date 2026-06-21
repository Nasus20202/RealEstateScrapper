"""Regression: IngestionService must enter the fetcher's async context.

The real BrowserFetcher launches Playwright in ``__aenter__`` and asserts in
``fetch()`` that it was entered. Nothing entered it at runtime, so every scrape
failed with "BrowserFetcher must be used as an async context manager". This test
locks in that ingest() enters a context-manager fetcher around the work — while
plain (non-context-manager) fetchers keep working unchanged (covered elsewhere).
"""
import pytest

from realestate.db.engine import create_session_factory
from realestate.ingestion.service import IngestionService
from realestate.models import Base
from realestate.scrapers.base import SearchCriteria
from tests.fixtures.loader import load_fixture


class _CtxFetcher:
    """Fetcher that is an async context manager and refuses to fetch unless
    entered — mirroring BrowserFetcher's contract."""

    def __init__(self):
        self.entered = False
        self.exited = False
        self.first = True

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def fetch(self, url: str) -> str:
        assert self.entered, "fetch() called before __aenter__"
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        empty = '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
        return f'<html><script id="__NEXT_DATA__" type="application/json">{empty}</script></html>'


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401  (rejestruje)

    saved = dict(base._REGISTRY)
    keep = {"otodom": base._REGISTRY["otodom"]}
    base._REGISTRY.clear()
    base._REGISTRY.update(keep)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def test_ingest_enters_and_exits_fetcher_context(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    fetcher = _CtxFetcher()
    svc = IngestionService(factory, fetcher)
    runs = await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=2)
    assert runs[0].status.value == "success"
    assert runs[0].new_count >= 20
    assert fetcher.entered is True
    assert fetcher.exited is True
