import pytest

from realestate.scrapers.base import ScraperBlocked, SearchCriteria
from realestate.scrapers.otodom import OtodomScraper
from realestate.scrapers.runner import run_search
from tests.fixtures.loader import load_fixture


class _FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.calls = []

    async def fetch(self, url: str) -> str:
        self.calls.append(url)
        # zwróć fixture dla strony 1, pustą listę-stronę dla kolejnych
        empty_page = (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}'
            "</script></html>"
        )
        return self.pages.get(url, empty_page)


@pytest.mark.asyncio
async def test_run_search_collects_and_dedups():
    scraper = OtodomScraper()
    url1 = scraper.build_search_url(SearchCriteria(city="gdansk"), 1)
    fetcher = _FakeFetcher({url1: load_fixture("otodom_search_gdansk")})
    listings = await run_search(scraper, fetcher, SearchCriteria(city="gdansk"), max_pages=3)
    assert len(listings) >= 20
    ids = [(x.source_id, x.external_id) for x in listings]
    assert len(ids) == len(set(ids))  # bez duplikatów


@pytest.mark.asyncio
async def test_run_search_stops_on_empty_page():
    scraper = OtodomScraper()
    fetcher = _FakeFetcher({})  # każda strona pusta
    listings = await run_search(scraper, fetcher, SearchCriteria(city="gdansk"), max_pages=5)
    assert listings == []
    # przerwał po pierwszej pustej stronie
    assert len(fetcher.calls) == 1


class _BlockingFetcher:
    async def fetch(self, url: str) -> str:
        raise ScraperBlocked(url)


@pytest.mark.asyncio
async def test_run_search_propagates_blocked():
    with pytest.raises(ScraperBlocked):
        criteria = SearchCriteria(city="gdansk")
        await run_search(
            OtodomScraper(), _BlockingFetcher(), criteria, max_pages=1
        )
