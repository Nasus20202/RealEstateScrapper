from datetime import UTC, datetime
from decimal import Decimal

from realestate.ingestion.normalize import compute_raw_hash, normalize_location, to_listing
from realestate.models.enums import ListingStatus, MarketType
from realestate.scrapers.base import RawListing


def _raw(**kw):
    base = dict(
        source_id="otodom",
        external_id="1",
        url="https://x/1",
        title="Mieszkanie",
        price=Decimal("600000"),
        area_m2=50.0,
        rooms=3,
        market="secondary",
        images=["b.jpg", "a.jpg"],
        attributes={"tags": ["BALCONY"]},
    )
    base.update(kw)
    return RawListing(**base)


def test_to_listing_maps_fields_and_computes_ppm2():
    now = datetime.now(UTC)
    listing = to_listing(_raw(), now=now)
    assert listing.source_id == "otodom" and listing.external_id == "1"
    assert listing.market == MarketType.SECONDARY
    assert listing.price_per_m2 == Decimal("12000.00")
    assert listing.status == ListingStatus.ACTIVE
    assert listing.first_seen == now and listing.last_seen == now
    assert listing.embedding is None
    assert listing.attributes == {"tags": ["BALCONY"]}
    assert listing.raw_hash


def test_unknown_market_is_none():
    assert to_listing(_raw(market=None), now=datetime.now(UTC)).market is None


def test_price_per_m2_none_when_no_price():
    listing = to_listing(_raw(price=None), now=datetime.now(UTC))
    assert listing.price_per_m2 is None


def test_raw_hash_stable_and_content_sensitive():
    h1 = compute_raw_hash(_raw())
    h2 = compute_raw_hash(_raw(images=["a.jpg", "b.jpg"]))  # different image order
    h3 = compute_raw_hash(_raw(price=Decimal("700000")))
    assert h1 == h2  # image order irrelevant (sorted)
    assert h1 != h3  # zmiana ceny zmienia hash


def test_normalize_location_generates_ascii_district_aliases():
    city, district, street = normalize_location("gdansk", "orunia sw wojciech lipce", None)

    assert city == "Gdańsk"
    assert district == "Orunia-Św. Wojciech-Lipce"
    assert street is None


def test_normalize_location_does_not_split_unknown_multiword_city():
    city, district, street = normalize_location("Pruszcz Gdański", None, None)

    assert city == "Pruszcz Gdański"
    assert district is None
    assert street is None
