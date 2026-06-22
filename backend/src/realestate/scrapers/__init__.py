import importlib
import pkgutil

from realestate.scrapers.base import (
    RawListing,
    Scraper,
    ScraperBlocked,
    SearchCriteria,
    get_scraper,
    get_scrapers,
    register,
)

# Infrastructure modules — they don't define a scraper plugin, so skip them.
_NON_PLUGIN_MODULES = {"base", "browser", "runner"}


def _load_plugins() -> None:
    """Import every scraper module in this package so its module-level
    ``register(...)`` call runs. Scrapers register via import side-effect; at
    runtime nothing imported them, leaving the registry empty (POST /scrape was a
    silent no-op). New scrapers are picked up automatically by dropping a file in
    this package — no edits here required.
    """
    for module in pkgutil.iter_modules(__path__):
        if module.name in _NON_PLUGIN_MODULES or module.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module.name}")


_load_plugins()

__all__ = [
    "RawListing",
    "Scraper",
    "ScraperBlocked",
    "SearchCriteria",
    "get_scraper",
    "get_scrapers",
    "register",
]
