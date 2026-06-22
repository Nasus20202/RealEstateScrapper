from realestate.scrapers.allcon import AllconScraper
from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.euro_styl import EuroStylScraper
from realestate.scrapers.invest_komfort import InvestKomfortScraper
from realestate.scrapers.morizon import _fix_gdansk_location, _split_location


def test_allcon_build_search_url_ascii_folds_gdansk():
    assert AllconScraper().build_search_url(SearchCriteria(city="Gdańsk"), 1).endswith("/gdansk")


def test_euro_styl_ignores_generic_search_category_links():
    html = """
    <html><body>
      <a href="/pl-pl/trojmiasto/wyniki-wyszukiwania-domy?type=dm">Domy</a>
      <a href="/pl-pl/trojmiasto/wyniki-wyszukiwania-apartamenty?type=as">Apartamenty</a>
    </body></html>
    """

    assert EuroStylScraper().parse_search(html) == []


def test_invest_komfort_ignores_city_landing_page_as_investment():
    html = '<html><body><a href="/pl/apartamenty/gdansk">Gdańsk</a></body></html>'

    assert InvestKomfortScraper().parse_search(html) == []


def test_morizon_keeps_gdansk_as_city_when_location_contains_only_district():
    city, district, _street = _split_location("Brętowo")
    city, district = _fix_gdansk_location("Mieszkanie Gdańsk Brętowo", city, district)

    assert city == "Gdańsk"
    assert district == "Brętowo"
