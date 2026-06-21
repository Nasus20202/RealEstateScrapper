from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.nieruchomosci_online import NieruchomosciOnlineScraper
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_listings():
    html = load_fixture("nieruchomosci_online_search_gdansk")
    listings = NieruchomosciOnlineScraper().parse_search(html)
    assert len(listings) >= 10
    first = listings[0]
    assert first.source_id == "nieruchomosci-online"
    assert first.external_id
    assert first.url.startswith("http")
    assert first.title


def test_listings_have_some_prices_and_areas():
    html = load_fixture("nieruchomosci_online_search_gdansk")
    listings = NieruchomosciOnlineScraper().parse_search(html)
    assert any(x.price is not None for x in listings)
    assert any(x.area_m2 is not None for x in listings)


def test_build_search_url_contains_city():
    url = NieruchomosciOnlineScraper().build_search_url(SearchCriteria(city="gdansk"), page=1)
    assert "gda" in url.lower()
