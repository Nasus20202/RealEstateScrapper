from realestate.scrapers.base import SearchCriteria
from realestate.scrapers.hossa import HossaScraper
from tests.fixtures.loader import load_fixture


def test_parse_search_returns_items():
    html = """
    <html><body>
      <article class="flat-card">
        <a href="/inwestycje/osiedle/flats/a-12/">A-12</a>
        <h3>A-12</h3>
        <span>549 000 zł</span>
        <span>42,5 m²</span>
        <span>2 pokoje</span>
        <img src="/media/a-12.jpg">
      </article>
    </body></html>
    """
    listings = HossaScraper().parse_search(html)
    assert len(listings) == 1
    first = listings[0]
    assert first.source_id == "hossa"
    assert first.url.startswith("http")
    assert first.title == "A-12"
    assert first.external_id
    assert first.price == 549000
    assert first.area_m2 == 42.5
    assert first.rooms == 2
    assert first.images == ["https://www.hossa.gda.pl/media/a-12.jpg"]


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
    assert "gdansk" in gdansk_url
    assert "gdynia" in gdynia_url
    assert gdansk_url != gdynia_url
