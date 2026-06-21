import subprocess
import sys


def test_builtin_scrapers_autoregister_on_package_import():
    """Regression: importing only `realestate.scrapers` (as the API and ingestion
    service do at runtime) must populate the registry. The bug was that scrapers
    register via import side-effect, but nothing imported the scraper modules at
    runtime — the empty registry made POST /scrape a silent no-op. Other tests
    import the scraper modules directly, which masked the gap, so this runs in a
    FRESH interpreter to reproduce the real runtime conditions.
    """
    code = "from realestate.scrapers import get_scrapers; print(sorted(get_scrapers()))"
    out = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    assert "otodom" in out
    assert "hossa" in out
    assert "nieruchomosci-online" in out
