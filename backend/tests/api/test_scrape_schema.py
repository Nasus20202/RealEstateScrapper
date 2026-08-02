"""ScrapeRequest schema: explicit mark_missing_gone control."""

from realestate.api.schemas import ScrapeRequest


def test_scrape_request_default_keeps_legacy_behavior():
    req = ScrapeRequest(city="Gdańsk")
    assert req.mark_missing_gone is None


def test_scrape_request_accepts_explicit_flag():
    assert ScrapeRequest(city="Gdańsk", mark_missing_gone=False).mark_missing_gone is False
    assert ScrapeRequest(mark_missing_gone=True).mark_missing_gone is True
