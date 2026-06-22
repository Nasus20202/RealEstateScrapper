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
    scrapers = {
        "adresowo",
        "allcon",
        "atal",
        "develia",
        "domesta",
        "ekolan",
        "euro-styl",
        "hossa",
        "invest-komfort",
        "morizon",
        "murapol",
        "nieruchomosci-online",
        "otodom",
        "pb-gorski",
        "robyg",
        "rynekpierwotny",
    }
    parsed = {s.strip("'\"") for s in out.strip("[]").split(", ")}
    missing = scrapers - parsed
    assert not missing, f"Missing scrapers in registry: {missing}"
