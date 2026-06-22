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
    assert first.title == "Garnizon"
    assert first.external_id
    assert first.city == "Gdańsk"
    assert first.district == "Wrzeszcz"
    assert first.street == "M. Hemara, B. Leśmiana"
    assert first.images == ["https://www.hossa.gda.pl/content/uploads/garnizon.jpg"]


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
