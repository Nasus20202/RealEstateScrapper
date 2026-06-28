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


def test_parse_search_falls_back_to_listing_links():
    html = """
    <html><body>
      <a href="/pl/oferta/2-pokojowe-mieszkanie-59m2-balkon-bezposrednio-ID4ynLg">
        <article><h2>2-pokojowe mieszkanie 59m2 + balkon Bezpośrednio</h2></article>
      </a>
      <a href="https://www.otodom.pl/pl/oferta/przymorze-2-pokoje-ID4BG3e">
        <article><h2>Przymorze | 2 pokoje</h2></article>
      </a>
    </body></html>
    """

    listings = OtodomScraper().parse_search(html)

    assert [listing.external_id for listing in listings] == ["ID4ynLg", "ID4BG3e"]
    assert listings[0].title == "2-pokojowe mieszkanie 59m2 + balkon Bezpośrednio"
    assert listings[0].url == (
        "https://www.otodom.pl/pl/oferta/2-pokojowe-mieszkanie-59m2-balkon-bezposrednio-ID4ynLg"
    )


def test_parse_search_expands_related_ads_instead_of_development_card():
    html = """
    <html><script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"data":{"searchAds":{"items":[{
      "id": 100,
      "title": "Meri Apartamenty",
      "slug": "meri-apartamenty-ID100",
      "relatedAds": [{
        "id": 101,
        "title": "4-pokojowe mieszkanie 86m2 + balkon",
        "slug": "4-pokojowe-mieszkanie-86m2-balkon-ID101",
        "totalPrice": {"value": 1530978},
        "areaInSquareMeters": 86.01,
        "roomsNumber": "FOUR"
      }, {
        "id": 102,
        "title": "3-pokojowe mieszkanie 56m2 + balkon",
        "slug": "3-pokojowe-mieszkanie-56m2-balkon-ID102",
        "totalPrice": {"value": 1023022},
        "areaInSquareMeters": 56.21,
        "roomsNumber": "THREE"
      }]
    }]}}}}}
    </script></html>
    """

    listings = OtodomScraper().parse_search(html)

    assert [listing.external_id for listing in listings] == ["101", "102"]
    assert listings[0].title == "4-pokojowe mieszkanie 86m2 + balkon"
    assert listings[0].price == Decimal("1530978")
    assert listings[0].rooms == 4


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
