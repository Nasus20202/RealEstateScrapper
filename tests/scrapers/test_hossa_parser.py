from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.hossa import HossaScraper
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_items():
    html = load_fixture("hossa_home")
    listings = HossaScraper().parse_search(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.source_id == "hossa"
    assert first.url.startswith("http")
    assert first.title
    assert first.external_id


def test_build_search_url_returns_listing_page():
    url = HossaScraper().build_search_url(SearchCriteria(city="gdansk"), page=1)
    assert url.startswith("https://")
    assert "hossa" in url


def test_build_search_url_city_specific():
    gdansk_url = HossaScraper().build_search_url(SearchCriteria(city="Gdańsk"), page=1)
    gdynia_url = HossaScraper().build_search_url(SearchCriteria(city="Gdynia"), page=1)
    assert "gdansk" in gdansk_url
    assert "gdynia" in gdynia_url
    assert gdansk_url != gdynia_url
