"""Normalizator RawListing -> Listing + raw_hash."""

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal

from realestate.locations import CITY_BY_KEY, DISTRICT_BY_KEY, location_key
from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing
from realestate.scrapers.base import RawListing


def _location_key(value: str | None) -> str:
    return location_key(value)


def normalize_location(
    city: str | None,
    district: str | None,
    street: str | None,
) -> tuple[str | None, str | None, str | None]:
    city_key = _location_key(city)
    district_key = _location_key(district)
    street_key = _location_key(street)

    city_match = CITY_BY_KEY.get(city_key)
    district_match = DISTRICT_BY_KEY.get(district_key)
    normalized_city = city_match or (city.strip(" ,") if city else None)
    normalized_district = (
        district_match.name if district_match else district.strip(" ,") if district else None
    )
    normalized_street = street.strip(" ,") if street else None

    city_as_district = DISTRICT_BY_KEY.get(city_key)
    if city_as_district:
        normalized_district = city_as_district.name
        normalized_city = city_as_district.city
    if district_key in CITY_BY_KEY:
        normalized_city = CITY_BY_KEY[district_key]
        normalized_district = None
    if street_key in CITY_BY_KEY:
        normalized_city = CITY_BY_KEY[street_key]
        normalized_street = None
    street_as_district = DISTRICT_BY_KEY.get(street_key)
    if street_as_district:
        normalized_district = normalized_district or street_as_district.name
        normalized_street = None

    if district_match and normalized_city not in CITY_BY_KEY.values():
        normalized_city = district_match.city

    if (
        district_key
        and district_key not in DISTRICT_BY_KEY
        and re.search(r"\b(ul\.|ulica|aleja|al\.|plac|skwer)\b", district_key)
    ):
        normalized_street = normalized_street or normalized_district
        normalized_district = None

    return normalized_city, normalized_district, normalized_street


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
    hash_obj = hashlib.sha256(canonical_json.encode("utf-8"))
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
    city, district, street = normalize_location(raw.city, raw.district, raw.street)

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
        city=city,
        district=district,
        street=street,
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
