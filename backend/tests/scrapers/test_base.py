import pytest
from pydantic import ValidationError

from realestate.scrapers.base import (
    RawListing,
    Scraper,
    ScraperBlocked,
    SearchCriteria,
    get_scraper,
    get_scrapers,
    register,
)


class _Dummy:
    source_id = "dummy"
    display_name = "Dummy"

    def build_search_url(self, criteria: SearchCriteria, page: int) -> str:
        return f"https://dummy/{criteria.city}?page={page}"

    def parse_search(self, html: str) -> list[RawListing]:
        return [RawListing(source_id="dummy", external_id="1", url="https://dummy/1", title="x")]

    def parse_detail(self, html: str, url: str) -> RawListing:
        return RawListing(source_id="dummy", external_id="1", url=url, title="x")


def test_raw_listing_defaults():
    rl = RawListing(source_id="s", external_id="e", url="u", title="t")
    assert rl.images == [] and rl.raw == {} and rl.price is None


def test_search_criteria_requires_city():
    with pytest.raises(ValidationError):
        SearchCriteria()
    assert SearchCriteria(city="gdansk").city == "gdansk"


def test_registry_register_and_get():
    d = _Dummy()
    register(d)
    assert get_scraper("dummy") is d
    assert "dummy" in get_scrapers()


def test_dummy_conforms_to_protocol():
    d = _Dummy()
    assert isinstance(d, Scraper)  # runtime_checkable Protocol


def test_scraper_blocked_is_exception():
    assert issubclass(ScraperBlocked, Exception)
