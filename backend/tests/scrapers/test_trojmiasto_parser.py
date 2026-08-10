from decimal import Decimal

from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.trojmiasto import TrojmiastoScraper, _split_location
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_listings():
    html = load_fixture("trojmiasto_search")
    listings = TrojmiastoScraper().parse_search(html)
    assert len(listings) >= 1
    first = listings[0]
    assert first.source_id == "trojmiasto"
    assert first.external_id
    assert first.url.startswith("http")
    assert first.title


def test_listings_have_prices_areas_rooms_and_floors():
    html = load_fixture("trojmiasto_search")
    listings = TrojmiastoScraper().parse_search(html)
    assert any(x.price is not None for x in listings)
    assert any(x.area_m2 is not None for x in listings)
    assert any(x.rooms is not None for x in listings)
    assert any(x.floor is not None for x in listings)


def test_parse_search_has_absolute_image_urls():
    html = load_fixture("trojmiasto_search")
    listings = TrojmiastoScraper().parse_search(html)
    with_images = [x for x in listings if x.images]
    assert with_images, "At least one card should have a thumbnail image"
    for listing in with_images:
        for img in listing.images:
            assert img.startswith("http")
            assert "placeholder" not in img


def test_parse_search_market_is_secondary():
    html = load_fixture("trojmiasto_search")
    listings = TrojmiastoScraper().parse_search(html)
    assert listings
    assert all(x.market == "secondary" for x in listings)


def test_build_search_url_default_secondary_page1():
    url = TrojmiastoScraper().build_search_url(SearchCriteria(city="gdansk"), page=1)
    assert "nieruchomosci-sprzedam-rynek-wtorny" in url
    assert "strona" not in url


def test_build_search_url_pagination():
    url = TrojmiastoScraper().build_search_url(SearchCriteria(city="gdansk"), page=2)
    assert "nieruchomosci-sprzedam-rynek-wtorny" in url
    assert url.endswith("?strona=2")


def test_build_search_url_primary_market():
    url = TrojmiastoScraper().build_search_url(
        SearchCriteria(city="gdansk", market="primary"), page=1
    )
    assert "nieruchomosci-sprzedam-rynek-pierwotny" in url


def test_parse_detail_extracts_fields():
    html = load_fixture("trojmiasto_detail")
    detail = TrojmiastoScraper().parse_detail(
        html,
        "https://ogloszenia.trojmiasto.pl/nieruchomosci-sprzedam-rynek-wtorny/"
        "sprzedam-3-pokojowe-mieszkanie-po-remoncie-gdansk-zaspa-rozstaje-ogl66444309.html",
    )
    assert detail.source_id == "trojmiasto"
    assert detail.external_id == "66444309"
    assert detail.title
    assert detail.description and "Mieszkanie 3 pokojowe" in detail.description
    assert detail.price == Decimal("980000")
    assert detail.area_m2 == 61.7
    assert detail.rooms == 3
    assert detail.floor == 10
    assert detail.attributes.get("construction_year") == 1980
    assert detail.city == "Gdańsk"
    assert detail.district == "Zaspa Rozstaje"
    assert detail.images
    assert len(detail.images) == len(set(detail.images))
    assert all(img.startswith("http") for img in detail.images)


def test_split_location_city_and_district():
    assert _split_location("Gdańsk Zaspa Rozstaje") == ("Gdańsk", "Zaspa Rozstaje", None)


def test_split_location_city_district_street():
    assert _split_location("Gdańsk Śródmieście, Lawendowa") == (
        "Gdańsk",
        "Śródmieście",
        "Lawendowa",
    )


def test_split_location_city_street():
    assert _split_location("Puck, Kolejowa") == ("Puck", None, "Kolejowa")


def test_split_location_multiword_district():
    assert _split_location("Gdynia Chwarzno - Wiczlino, Stanisława Filipkowskiego") == (
        "Gdynia",
        "Chwarzno - Wiczlino",
        "Stanisława Filipkowskiego",
    )


def test_split_location_postal_code_not_district():
    assert _split_location("80-180, Gdańsk") == ("Gdańsk", None, "80-180")


def test_split_location_unknown_city_degrades():
    assert _split_location("Jakieś Osobliwe Miejsce") == (None, "Jakieś Osobliwe Miejsce", None)
