from decimal import Decimal

from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.hossa import HossaScraper
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_items():
    html = """
    <html><body>
      <div class="o-card type-a" data-src="/content/uploads/garnizon.jpg">
        <div class="o-card__inner">
          <div class="o-card__label">Nowa oferta</div>
          <h2 class="o-card__name">Garnizon</h2>
          <p class="o-card__place">Gdańsk Wrzeszcz</p>
          <p class="o-card__address separated--slash">
            ul. <span>M. Hemara</span><span>B. Leśmiana</span>
          </p>
          <a href="/garnizon-loftyapartamenty/" class="btn btn--light transparent">Więcej</a>
        </div>
      </div>
    </body></html>
    """
    listings = HossaScraper().parse_search(html)
    assert len(listings) == 1
    first = listings[0]
    assert first.source_id == "hossa"
    assert first.url.startswith("http")
    assert "/api/apartments/" in first.url
    assert first.title == "Garnizon"
    assert first.external_id
    assert first.city == "Gdańsk"
    assert first.district == "Wrzeszcz"
    assert first.street == "M. Hemara, B. Leśmiana"
    assert first.images == ["https://www.hossa.gda.pl/content/uploads/garnizon.jpg"]


def test_parse_detail_api_returns_concrete_apartments():
    body = """
    {"data":[{"id":6243,"investment_slug":"garnizon-loftyapartamenty","number":"GR/L4/315",
    "floor":3,"rooms":1,"area_usable":"58.23","description":"Balkon i garaż",
    "price":"958698.72","building":"Leśmiana 4","availability":"2028-3",
    "status_label":"dostępny","price_per_usable_m2":"16464.00","tags":["Balkon"],
    "media":[{"picture":"/content/uploads/plans/04/projection.jpg"}]}]}
    """
    listings = HossaScraper().parse_detail(
        body,
        "https://www.hossa.gda.pl/api/apartments/?inv=garnizon-loftyapartamenty&type=a",
    )
    assert isinstance(listings, list)
    first = listings[0]
    assert first.external_id == "apartment-6243"
    assert first.title == "Garnizon Loftyapartamenty GR/L4/315"
    assert first.price == Decimal("958698.72")
    assert first.area_m2 == 58.23
    assert first.rooms == 1
    assert first.floor == 3
    assert first.city == "Gdańsk"
    assert first.district == "Wrzeszcz Górny"
    assert first.street == "Garnizon"
    assert first.lat == 54.3845063
    assert first.lon == 18.5928283
    assert first.description == "Balkon i garaż"
    assert first.attributes["tags"] == ["Balkon"]
    assert first.images == ["https://www.hossa.gda.pl/content/uploads/plans/04/projection.jpg"]


def test_parse_detail_api_sets_wiszace_ogrody_coordinates():
    body = '{"data":[{"id":1,"number":"WO/1","rooms":2,"area":"45","price":"600000"}]}'
    listings = HossaScraper().parse_detail(
        body,
        "https://www.hossa.gda.pl/api/apartments/?inv=wiszace-ogrody&type=a",
    )
    assert isinstance(listings, list)
    first = listings[0]
    assert first.city == "Gdańsk"
    assert first.district == "Kiełpinek"
    assert first.street == "Taneczna 13"
    assert first.lat == 54.3531938
    assert first.lon == 18.5319615


def test_parse_search_ignores_category_links():
    html = load_fixture("hossa_home")
    listings = HossaScraper().parse_search(html)
    titles = {listing.title for listing in listings}
    assert "Mieszkania w Gdańsku" not in titles
    assert "Mieszkania" not in titles


def test_build_search_url_returns_listing_page():
    url = HossaScraper().build_search_url(SearchCriteria(city="gdansk"), page=1)
    assert url.startswith("https://")
    assert "hossa" in url


def test_build_search_url_city_specific():
    gdansk_url = HossaScraper().build_search_url(SearchCriteria(city="Gdańsk"), page=1)
    gdynia_url = HossaScraper().build_search_url(SearchCriteria(city="Gdynia"), page=1)
    assert gdansk_url.endswith("/mieszkania/")
    assert gdynia_url.endswith("/mieszkania/")
