from decimal import Decimal

from realestate.scrapers.pb_gorski import PBGorskiScraper
from tests.fixtures.loader import load_fixture


def _apartments():
    html = load_fixture("pb_gorski_pileckiego_5")
    result = PBGorskiScraper().parse_detail(
        html,
        "https://pbgorski.pl/inwestycja/pileckiego-5/",
    )
    assert isinstance(result, list)
    return result


def test_parse_detail_returns_apartments():
    apartments = _apartments()
    assert len(apartments) > 10


def test_parses_apartment_fields():
    by_title = {a.title: a for a in _apartments()}
    flat = by_title["Mieszkanie 32"]
    assert flat.external_id == "pileckiego-5-mieszkanie-32"
    assert flat.price == Decimal("2739777")
    assert flat.area_m2 == 100.27
    assert flat.rooms == 4
    assert flat.floor == 4
    assert flat.city == "Gdańsk"
    assert flat.market == "primary"
    assert flat.attributes["investment"] == "pileckiego-5"
    assert flat.attributes["flat_id"] == "mieszkanie-32"


def test_marks_reserved_apartments():
    by_title = {a.title: a for a in _apartments()}
    assert by_title["Mieszkanie 21"].attributes["status"] == "reserved"


def test_external_ids_are_unique():
    apartments = _apartments()
    ids = [a.external_id for a in apartments]
    assert len(ids) == len(set(ids))


def test_parse_search_deduplicates_utm_investment_links():
    html = """
    <html><body>
      <a href="/inwestycja/sw-piotra-6/">Św. Piotra 6</a>
      <a href="/inwestycja/sw-piotra-6/?utm_source=www&utm_medium=popup">Św. Piotra 6</a>
    </body></html>
    """
    listings = PBGorskiScraper().parse_search(html)
    assert len(listings) == 1
    assert listings[0].external_id == "sw-piotra-6"
    assert listings[0].url == "https://pbgorski.pl/inwestycja/sw-piotra-6/"
