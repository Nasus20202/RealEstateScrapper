from realestate.scrapers.develia import DeveliaScraper
from realestate.scrapers.domesta import DomestaScraper
from realestate.scrapers.pb_gorski import PBGorskiScraper


def test_develia_does_not_emit_investment_fallback_as_flat():
    result = DeveliaScraper().parse_detail(
        "<html><body><h1>Żywiecka Vita</h1></body></html>",
        "https://develia.pl/pl/mieszkania/gdansk/zywiecka-vita/",
    )

    assert result == []


def test_domesta_does_not_emit_investment_fallback_as_flat():
    result = DomestaScraper().parse_detail(
        "<html><body><h1>GreenLine</h1></body></html>",
        "https://www.domesta.com.pl/gdansk/greenline",
    )

    assert result == []


def test_pb_gorski_does_not_emit_investment_fallback_as_flat():
    result = PBGorskiScraper().parse_detail(
        "<html><body><h1>Osiedle Srebrniki</h1></body></html>",
        "https://pbgorski.pl/inwestycja/osiedle-srebrniki/",
    )

    assert result == []
