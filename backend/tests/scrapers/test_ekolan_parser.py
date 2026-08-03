"""Ekolan.pl scraper parser tests.

Coverage for the developer-style flow: the search page yields investment
containers that must expand into real apartments (never data-less stubs or
hash-based garbage IDs) via getApartments.htm tables/cards or the main-page
house-item list.
"""

from realestate.scrapers.ekolan import EkolanScraper
from tests.fixtures.loader import load_fixture


def _scraper() -> EkolanScraper:
    return EkolanScraper()


def _no_get_apartments(url: str) -> str:
    raise RuntimeError("getApartments.htm unavailable")


def test_parse_search_returns_investment_containers():
    listings = _scraper().parse_search(load_fixture("ekolan_search_oferta"))

    assert len(listings) == 4
    assert all(item.is_container for item in listings)
    titles = {item.title for item in listings}
    assert {"KRZYWOUSTEGO", "ALTRO", "GUDERSKIEGO", "NAVIGARE"} <= titles


def test_parse_detail_navigare_cards(monkeypatch):
    scraper = _scraper()
    monkeypatch.setattr(
        "realestate.scrapers.ekolan.fetch_text",
        lambda url: load_fixture("ekolan_navigare_apartments"),
    )
    result = scraper.parse_detail(
        load_fixture("ekolan_navigare_apartments"), "https://navigare.ekolan.pl"
    )

    assert isinstance(result, list)
    assert len(result) >= 5
    for item in result:
        assert item.external_id.startswith("navigare-")
        assert item.price is not None and item.price >= 1000
        assert item.area_m2 is not None
        assert item.rooms is not None


def test_parse_detail_altro_table(monkeypatch):
    scraper = _scraper()
    monkeypatch.setattr(
        "realestate.scrapers.ekolan.fetch_text",
        lambda url: load_fixture("ekolan_altro_apartments"),
    )
    result = scraper.parse_detail(
        load_fixture("ekolan_altro_apartments"), "https://altro.ekolan.pl"
    )

    assert isinstance(result, list)
    assert len(result) >= 5
    for item in result:
        assert item.external_id.startswith("altro-")
        assert item.price is not None and item.price >= 1000
        assert item.area_m2 is not None


def test_parse_detail_krzywoustego_house_items(monkeypatch):
    scraper = _scraper()
    monkeypatch.setattr("realestate.scrapers.ekolan.fetch_text", _no_get_apartments)
    result = scraper.parse_detail(
        load_fixture("ekolan_krzywoustego"), "https://krzywoustego.ekolan.pl/"
    )

    assert isinstance(result, list)
    assert len(result) >= 5
    for item in result:
        assert item.external_id.startswith("krzywoustego-")
        assert item.price is not None and item.price >= 1000
        assert item.area_m2 is not None
        assert item.rooms is not None


def test_parse_search_filters_by_ascii_folded_city():
    scraper = _scraper()
    # parse_search filters against the last city set by build_search_url
    scraper._last_city = "gdansk"
    listings = scraper.parse_search(load_fixture("ekolan_search_oferta"))

    assert listings
    assert all(item.city == "Gdańsk" for item in listings)
    # ALTRO is in Rumia and must be excluded even though 'gdansk' != 'Gdańsk' textually
    assert {item.title for item in listings} >= {"KRZYWOUSTEGO", "NAVIGARE"}
    assert "ALTRO" not in {item.title for item in listings}


def test_parse_detail_guderskiego_returns_empty(monkeypatch):
    scraper = _scraper()
    monkeypatch.setattr("realestate.scrapers.ekolan.fetch_text", _no_get_apartments)
    result = scraper.parse_detail(
        load_fixture("ekolan_guderskiego"), "https://guderskiego.ekolan.pl/"
    )

    assert result == []
