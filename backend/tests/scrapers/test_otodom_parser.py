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


def test_build_search_url_ascii_folds_polish_diacritics():
    # Regression: a diacritic city slug ("gdańsk") makes otodom 301-redirect to
    # /cala-polska?fromInvalidLocation=true (all of Poland). The slug must be
    # ASCII-folded so users typing "Gdańsk"/"Gdynia" get the right city.
    url = OtodomScraper().build_search_url(SearchCriteria(city="Gdańsk"), page=1)
    assert "/pomorskie/gdansk" in url
    assert "gdańsk" not in url and "gdańsk" not in url


def test_build_search_url_slugifies_multiword_city():
    url = OtodomScraper().build_search_url(SearchCriteria(city="Gdańsk Wrzeszcz"), page=1)
    assert "/pomorskie/gdansk-wrzeszcz" in url


def test_market_heuristic_few_nones():
    """After the obido/source heuristic, nearly all listings should have a market value."""
    html = load_fixture("otodom_search_gdansk")
    listings = OtodomScraper().parse_search(html)
    none_count = sum(1 for x in listings if x.market is None)
    # Only listings with source=None remain unresolved; fixture has exactly 1 such item
    assert none_count <= 2, f"Too many market=None listings: {none_count}"
    # Non-obido sourced items should be secondary, not None
    secondary = [x for x in listings if x.market == "secondary"]
    assert len(secondary) >= 8, f"Expected at least 8 secondary listings, got {len(secondary)}"


def test_posted_at_populated():
    """At least one listing should have a non-None posted_at from dateCreated."""
    html = load_fixture("otodom_search_gdansk")
    listings = OtodomScraper().parse_search(html)
    with_posted = [x for x in listings if x.posted_at is not None]
    assert len(with_posted) >= 1, "Expected at least one listing with posted_at set"
