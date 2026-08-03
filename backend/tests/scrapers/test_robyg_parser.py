"""Robyg.pl scraper parser tests.

The investment page renders its apartments as a table of ``.item[data-id]``
rows. Those rows carry no ``<img>`` tags, so unit images must be recovered from
the per-unit floor-plan / 3D-tour URLs (``data-plan-thumb`` and the
deterministic ``property-floor-plan/{flat_id}`` pattern) plus the investment's
own gallery/visualization photos.
"""

from realestate.scrapers.robyg import RobygScraper
from tests.fixtures.loader import load_fixture


def _scraper() -> RobygScraper:
    return RobygScraper()


def test_parse_detail_apartments_carry_images():
    result = _scraper().parse_detail(
        load_fixture("robyg_metro_life"),
        "https://www.robyg.pl/warszawa/inwestycje/metro-life",
    )

    assert isinstance(result, list)
    assert len(result) >= 20
    assert all(item.images for item in result)


def test_parse_detail_apartments_include_floor_plan():
    result = _scraper().parse_detail(
        load_fixture("robyg_metro_life"),
        "https://www.robyg.pl/warszawa/inwestycje/metro-life",
    )

    assert isinstance(result, list)
    by_id = {item.attributes["flat_id"]: item for item in result}
    assert "122579" in by_id
    assert any("property-floor-plan/122579-large-1.png" in img for img in by_id["122579"].images)


def test_parse_detail_apartments_carry_investment_gallery_photo():
    result = _scraper().parse_detail(
        load_fixture("robyg_metro_life"),
        "https://www.robyg.pl/warszawa/inwestycje/metro-life",
    )

    assert isinstance(result, list)
    first = result[0]
    assert any("metro-life-3973-original-0-1.jpg" in img for img in first.images)


def test_parse_detail_apartments_carry_3d_tour_thumb_when_present():
    result = _scraper().parse_detail(
        load_fixture("robyg_metro_life"),
        "https://www.robyg.pl/warszawa/inwestycje/metro-life",
    )

    assert isinstance(result, list)
    by_id = {item.attributes["flat_id"]: item for item in result}
    assert "122579" in by_id
    assert any(
        "tours.3destate.pl/apartamenty-metro-life/amc-ab-c-0-3.0.3d.top" in img
        for img in by_id["122579"].images
    )
