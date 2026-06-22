"""Normalizator RawListing -> Listing + raw_hash."""
import hashlib
import json
from datetime import datetime
from decimal import Decimal

from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing
from realestate.scrapers.base import RawListing


def compute_raw_hash(raw: RawListing) -> str:
    """Compute SHA-256 hash of canonical JSON of significant fields.

    Fields: title, price, area_m2, rooms, floor, total_floors, city, district,
    street, market, description, attributes, sorted(images). Images are sorted to ensure
    order doesn't affect the hash. Decimal and datetime objects are serialized
    as strings.
    """
    payload = {
        "title": raw.title,
        "price": raw.price,
        "area_m2": raw.area_m2,
        "rooms": raw.rooms,
        "floor": raw.floor,
        "total_floors": raw.total_floors,
        "city": raw.city,
        "district": raw.district,
        "street": raw.street,
        "market": raw.market,
        "description": raw.description,
        "attributes": raw.attributes,
        "images": sorted(raw.images),
    }

    # Serialize with sorted keys, ensure_ascii=False, and default=str for Decimal/datetime
    canonical_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    hash_obj = hashlib.sha256(canonical_json.encode('utf-8'))
    return hash_obj.hexdigest()


def to_listing(raw: RawListing, *, now: datetime) -> Listing:
    """Map RawListing to transient Listing model.

    Args:
        raw: The raw scraping result
        now: Current datetime to set as first_seen and last_seen

    Returns:
        Listing: A transient Listing instance with computed fields
    """
    # Map market string to MarketType enum
    market = None
    if raw.market == "primary":
        market = MarketType.PRIMARY
    elif raw.market == "secondary":
        market = MarketType.SECONDARY
    # else market remains None

    # Compute price_per_m2
    price_per_m2 = None
    if raw.price is not None and raw.area_m2 and raw.area_m2 > 0:
        price_per_m2 = round(Decimal(raw.price) / Decimal(str(raw.area_m2)), 2)

    # Compute raw hash
    raw_hash = compute_raw_hash(raw)

    # Create and return the Listing
    return Listing(
        source_id=raw.source_id,
        external_id=raw.external_id,
        url=raw.url,
        title=raw.title,
        price=raw.price,
        price_per_m2=price_per_m2,
        area_m2=raw.area_m2,
        rooms=raw.rooms,
        floor=raw.floor,
        total_floors=raw.total_floors,
        city=raw.city,
        district=raw.district,
        street=raw.street,
        lat=raw.lat,
        lon=raw.lon,
        market=market,
        description=raw.description,
        attributes=raw.attributes,
        images=raw.images,
        posted_at=raw.posted_at,
        raw_hash=raw_hash,
        status=ListingStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        embedding=None,
    )
