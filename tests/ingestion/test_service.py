import pytest

from realestate.db.engine import create_session_factory
from realestate.ingestion.service import IngestionService
from realestate.models import Base, ScrapeRunStatus
from realestate.repositories.listings import ListingRepository
from realestate.scrapers.base import ScraperBlocked, SearchCriteria
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    """Zwraca fixture otodom dla 1. strony, pustą stronę dla kolejnych."""
    def __init__(self):
        self.first = True
    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        empty = '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
        return f'<html><script id="__NEXT_DATA__" type="application/json">{empty}</script></html>'


async def _schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def _only_otodom():
    # ogranicz rejestr do otodom dla determinizmu; snapshot/restore (ten katalog
    # nie ma globalnego fixture izolującego rejestr — przywróć go sam).
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401  (rejestruje)
    saved = dict(base._REGISTRY)
    keep = {"otodom": base._REGISTRY["otodom"]}
    base._REGISTRY.clear()
    base._REGISTRY.update(keep)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def test_ingest_inserts_listings_and_records_run(engine):
    await _schema(engine)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())
    runs = await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=2)
    assert len(runs) == 1
    run = runs[0]
    assert run.source_id == "otodom"
    assert run.status == ScrapeRunStatus.SUCCESS
    assert run.new_count >= 20
    assert run.finished_at is not None
    async with factory() as s:
        assert await ListingRepository(s).count_active() >= 20


class _BlockedFetcher:
    async def fetch(self, url: str) -> str:
        raise ScraperBlocked(url)


async def test_ingest_records_blocked_without_crashing(engine):
    await _schema(engine)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _BlockedFetcher())
    runs = await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=1)
    assert runs[0].status == ScrapeRunStatus.BLOCKED
    assert runs[0].error_message
