from decimal import Decimal

from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.otodom import OtodomScraper
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_listings():
    html = load_fixture("otodom_search_gdansk")
    listings = OtodomScraper().parse_search(html)
    # fixture zawiera ~34 pozycje w searchAds.items
    assert len(listings) >= 20
    first = listings[0]
    assert first.source_id == "otodom"
    assert first.external_id  # niepuste
    assert first.url.startswith("https://www.otodom.pl/")
    assert first.title


def test_parse_search_extracts_numeric_fields():
    html = load_fixture("otodom_search_gdansk")
    listings = OtodomScraper().parse_search(html)
    priced = [x for x in listings if x.price is not None]
    assert priced, "co najmniej jedna oferta ma cenę"
    assert all(isinstance(x.price, Decimal) for x in priced)
    witharea = [x for x in listings if x.area_m2 is not None]
    assert witharea and all(x.area_m2 > 0 for x in witharea)


def test_build_search_url_contains_city():
    url = OtodomScraper().build_search_url(SearchCriteria(city="gdansk"), page=2)
    assert "gdansk" in url.lower()
    assert "page=2" in url or "/2" in url
