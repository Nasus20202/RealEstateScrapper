from decimal import Decimal

from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.nieruchomosci_online import (
    NieruchomosciOnlineScraper,
    _area,
    _money,
    _split_address,
)
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


def test_parse_search_has_images():
    html = load_fixture("nieruchomosci_online_search_gdansk")
    listings = NieruchomosciOnlineScraper().parse_search(html)
    with_images = [x for x in listings if x.images]
    assert len(with_images) >= 1, "At least one tile should have a thumbnail image"
    assert all(img.startswith("http") for x in with_images for img in x.images)


def test_parse_detail_extracts_gallery_images_as_absolute_urls():
    html = """
    <html><body>
      <h1>Mieszkanie testowe</h1>
      <div class="description">Opis detalu</div>
      <div class="gallery">
        <img src="/media/a.jpg">
        <img data-src="//img.nieruchomosci-online.pl/b.jpg">
        <img src="https://www.nieruchomosci-online.pl/media/a.jpg">
      </div>
    </body></html>
    """
    detail = NieruchomosciOnlineScraper().parse_detail(
        html, "https://www.nieruchomosci-online.pl/oferta/123.html"
    )
    assert detail.images == [
        "https://www.nieruchomosci-online.pl/media/a.jpg",
        "https://img.nieruchomosci-online.pl/b.jpg",
    ]


def test_parse_detail_prefers_title_street_over_contact_json_ld_address():
    html = """
    <html><head>
      <script type="application/ld+json">
      {"@type":"Organization","address":{"addressLocality":"Gdańsk",
      "addressRegion":"Przymorze","streetAddress":"ul. Kardynała Stefana Wyszyńskiego 1"}}
      </script>
    </head><body>
      <h1>Apartament z garażem, ul. Kaczyńskiego</h1>
    </body></html>
    """

    detail = NieruchomosciOnlineScraper().parse_detail(
        html, "https://www.nieruchomosci-online.pl/oferta/123.html"
    )

    assert detail.street == "ul. Kaczyńskiego"


def test_build_search_url_contains_city():
    url = NieruchomosciOnlineScraper().build_search_url(SearchCriteria(city="gdansk"), page=1)
    assert "gda" in url.lower()


def test_money_handles_polish_separators():
    assert _money("568\xa0292 zł") == Decimal("568292")
    assert _money("1.200.500 zł") == Decimal("1200500")
    assert _money("brak") is None


def test_area_handles_polish_decimal():
    assert _area("32,58 m²") == 32.58
    assert _area("1.234,56 m²") == 1234.56
    assert _area("") is None


def test_split_address_keeps_code_out_of_district():
    city, district, street = _split_address("10-457, Gdańsk")

    assert city == "Gdańsk"
    assert district is None
    assert street == "10-457"


def test_split_address_keeps_street_out_of_district():
    city, district, street = _split_address("Aleja Niepodległości, Sopot")

    assert city == "Sopot"
    assert district is None
    assert street == "Aleja Niepodległości"
