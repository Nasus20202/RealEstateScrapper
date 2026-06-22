from realestate.scrapers.adresowo import AdresowoScraper
from realestate.scrapers.base import SearchCriteria


def _card(data_id: str, href: str, location: str, street: str) -> str:
    return f"""
    <div data-offer-card data-id="{data_id}">
      <h2>
        <a href="{href}">
          <span class="font-bold">{location}</span>
          <span class="text-neutral-900">{street}</span>
        </a>
      </h2>
      <div class="flex"><p><span class="font-bold">500 000</span> zł</p></div>
      <div class="flex"><p><span class="font-bold">50</span> m²</p></div>
      <div class="flex"><p><span class="font-bold">2</span> pok.</p></div>
    </div>
    """


def test_parse_search_filters_out_other_cities_after_build_search_url():
    scraper = AdresowoScraper()
    scraper.build_search_url(SearchCriteria(city="Gdańsk"), page=1)
    html = f"""
    <html><body>
      {_card("1", "/o/mieszkanie-gdansk-abc1", "Gdańsk Oliwa", "ul. Spacerowa")}
      {_card("2", "/o/mieszkanie-wroclaw-def2", "Wrocław Krzyki", "ul. Testowa")}
      {_card("3", "/o/mieszkanie-lublin-ghi3", "Lublin", "ul. Testowa")}
    </body></html>
    """

    listings = scraper.parse_search(html)

    assert [listing.external_id for listing in listings] == ["1"]
    assert listings[0].city == "Gdańsk"
