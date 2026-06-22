from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.db.engine import create_session_factory
from realestate.events.bus import EventBus
from realestate.models import Base
from realestate.models.user_data import SavedSearch
from realestate.scheduler.job import run_scheduled_scrape
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True

    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        empty = '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
        return f'<html><script id="__NEXT_DATA__" type="application/json">{empty}</script></html>'


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch, pg_url):
    monkeypatch.setenv("DATABASE_URL", pg_url)


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


async def test_job_runs_ingest_for_saved_search_with_city(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add(
            SavedSearch(
                name="gda",
                filters={"city": "gdansk", "max_pages": 2},
                nl_query=None,
                created_at=datetime.now(UTC),
            )
        )
        s.add(
            SavedSearch(
                name="bez miasta",
                filters={"max_price": 500000},
                nl_query=None,
                created_at=datetime.now(UTC),
            )
        )
        await s.commit()

    bus = EventBus()
    processed = await run_scheduled_scrape(factory, _OneSourceFetcher(), bus, max_pages=2)
    assert processed == 1  # tylko wyszukiwanie z miastem

    # zweryfikuj, że powstały oferty
    from realestate.repositories.listings import ListingRepository

    async with AsyncSession(engine, expire_on_commit=False) as s:
        assert await ListingRepository(s).count_active() >= 20


async def test_job_uses_default_cities_without_saved_searches(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    bus = EventBus()
    assert await run_scheduled_scrape(factory, _OneSourceFetcher(), bus) == 3
