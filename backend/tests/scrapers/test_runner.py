import pytest

from realestate.scrapers.base import RawListing, ScraperBlocked, SearchCriteria
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


class _DetailScraper:
    source_id = "detail-source"
    display_name = "Detail source"

    def build_search_url(self, criteria: SearchCriteria, page: int) -> str:
        return "https://example.test/search"

    def parse_search(self, html: str) -> list[RawListing]:
        return [
            RawListing(
                source_id=self.source_id,
                external_id="1",
                url="https://example.test/detail/1",
                title="Search title",
                city="Gdańsk",
                images=["https://example.test/search.jpg"],
            )
        ]

    def parse_detail(self, html: str, url: str) -> RawListing:
        return RawListing(
            source_id=self.source_id,
            external_id="1",
            url=url,
            title="Detail title",
            street="Morska",
            description="Detail description",
            images=["https://example.test/search.jpg", "https://example.test/detail.jpg"],
        )


class _DetailFetcher:
    async def fetch(self, url: str) -> str:
        return "<html></html>"


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
        await run_search(OtodomScraper(), _BlockingFetcher(), criteria, max_pages=1)


@pytest.mark.asyncio
async def test_run_search_can_enrich_from_detail_pages():
    logs: list[str] = []

    async def on_log(message: str) -> None:
        logs.append(message)

    listings = await run_search(
        _DetailScraper(),
        _DetailFetcher(),
        SearchCriteria(city="Gdańsk"),
        max_pages=1,
        fetch_details=True,
        on_log=on_log,
    )
    assert listings[0].title == "Search title"
    assert listings[0].street == "Morska"
    assert listings[0].description == "Detail description"
    assert listings[0].images == [
        "https://example.test/search.jpg",
        "https://example.test/detail.jpg",
    ]
    assert any("Pobieram stronę 1" in log for log in logs)
    assert any("Pobieram szczegóły" in log for log in logs)
