"""IngestionService geocodes addresses into listings.lat/lon at ingestion."""

import pytest

from realestate.db.engine import create_session_factory
from realestate.ingestion.service import IngestionService
from realestate.models import Base
from realestate.repositories.listings import ListingRepository
from realestate.scrapers.base import SearchCriteria
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


class _FakeGeocoder:
    def __init__(self):
        self.queries: list[str] = []

    async def geocode(self, query: str):
        self.queries.append(query)
        return (54.35, 18.65)


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


async def test_ingest_fills_lat_lon_via_geocoder(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    geocoder = _FakeGeocoder()
    svc = IngestionService(factory, _OneSourceFetcher(), geocoder=geocoder)
    await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=1)

    assert geocoder.queries, "geocoder should have been called for addressed listings"
    async with factory() as s:
        listings = await ListingRepository(s).list_active(limit=100, offset=0)
        geocoded = [x for x in listings if x.lat is not None]
        assert geocoded, "at least some listings should be geocoded"
        assert geocoded[0].lat == 54.35
        assert geocoded[0].lon == 18.65


async def test_ingest_without_geocoder_leaves_coords_null(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())  # no geocoder
    await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"], max_pages=1)
    async with factory() as s:
        listings = await ListingRepository(s).list_active(limit=100, offset=0)
        assert listings
        assert all(x.lat is None for x in listings)
