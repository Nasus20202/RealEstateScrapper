from .loader import load_fixture


def test_load_otodom_fixture():
    html = load_fixture("otodom_search_gdansk")
    assert "__NEXT_DATA__" in html
    assert len(html) > 100_000


def test_load_nieruchomosci_fixture():
    html = load_fixture("nieruchomosci_online_search_gdansk")
    assert len(html) > 100_000


def test_load_hossa_fixture():
    html = load_fixture("hossa_home")
    assert len(html) > 10_000
