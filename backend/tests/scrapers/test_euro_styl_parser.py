from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.euro_styl import EuroStylScraper

_API_PAYLOAD = {
    "investments": [
        {
            "id": "inv1",
            "name": "DOKI",
            "city": "Gdańsk",
            "district": "Przymorze",
            "street": "ul. Testowa",
            "flats": [
                {
                    "id": "f1",
                    "flat": "1",
                    "area": "67,40 m<sup>2</sup>",
                    "rooms": "3 pokoje z aneksem",
                    "floor": "1 <span>piętro</span>",
                    "price": {"new": "1000000"},
                    "picture": {"img": "/getmedia/xxx/Rzut%203D_1.png?width=276"},
                },
                {
                    "id": "f2",
                    "flat": "2",
                    "area": "40,58 m²",
                    "rooms": "2 pokoje",
                    "floor": "parter",
                    "price": {"old": "500000"},
                    "picture": {"img": "/getmedia/yyy/ikonka.svg"},
                },
            ],
        }
    ]
}


def _listings(monkeypatch):
    scraper = EuroStylScraper()
    scraper.build_search_url(SearchCriteria(city="Gdańsk"), page=1)
    monkeypatch.setattr("realestate.scrapers.euro_styl.fetch_json", lambda url: _API_PAYLOAD)
    return scraper.parse_search("ignored")


def test_parse_search_returns_listings(monkeypatch):
    listings = _listings(monkeypatch)
    assert len(listings) == 2
    assert {x.external_id for x in listings} == {"inv1-f1", "inv1-f2"}
    assert all(x.title for x in listings)


def test_parse_search_keeps_floor_plans_but_filters_icons(monkeypatch):
    """Euro Styl exposes floor plans ('Rzut 3D' PNGs) and UI icons (SVGs) —
    floor plans are better than nothing, but the SVG icons must be dropped."""
    listings = _listings(monkeypatch)
    assert listings
    assert listings[0].images == [
        "https://www.eurostyl.com.pl/getmedia/xxx/Rzut%203D_1.png?width=276"
    ]
    assert listings[1].images == []


def test_parse_search_extracts_numeric_fields(monkeypatch):
    listings = _listings(monkeypatch)
    assert [x.area_m2 for x in listings] == [67.4, 40.58]
    assert [x.rooms for x in listings] == [3, 2]
    assert [x.floor for x in listings] == [1, 0]
    assert [x.market for x in listings] == ["primary", "primary"]
    assert [x.city for x in listings] == ["Gdańsk", "Gdańsk"]
