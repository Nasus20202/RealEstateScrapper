"""Normalizator RawListing -> Listing + raw_hash."""

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal

from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing
from realestate.scrapers.base import RawListing

KNOWN_CITIES = {
    "gdansk": "Gdańsk",
    "gdańsk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
}

KNOWN_DISTRICTS = {
    "aniolki": "Aniołki",
    "aniołki": "Aniołki",
    "brzezno": "Brzeźno",
    "brzeźno": "Brzeźno",
    "chelm": "Chełm",
    "chełm": "Chełm",
    "dolny sopot": "Dolny Sopot",
    "dzialki lesne": "Działki Leśne",
    "działki leśne": "Działki Leśne",
    "gorny sopot": "Górny Sopot",
    "górny sopot": "Górny Sopot",
    "jasien": "Jasień",
    "jasień": "Jasień",
    "karwiny": "Karwiny",
    "letnica": "Letnica",
    "maly kack": "Mały Kack",
    "mały kack": "Mały Kack",
    "morena": "Morena",
    "oliwa": "Oliwa",
    "orlowo": "Orłowo",
    "orłowo": "Orłowo",
    "osowa": "Osowa",
    "piecki-migowo": "Piecki-Migowo",
    "przymorze": "Przymorze",
    "redlowo": "Redłowo",
    "redłowo": "Redłowo",
    "srodmiescie": "Śródmieście",
    "śródmieście": "Śródmieście",
    "ujeścisko": "Ujeścisko",
    "ujescisko": "Ujeścisko",
    "witomino": "Witomino",
    "wrzeszcz": "Wrzeszcz",
    "zaspa": "Zaspa",
    "zabianka": "Żabianka",
    "żabianka": "Żabianka",
    "brętowo": "Brętowo",
    "bretowo": "Brętowo",
    "orunia-św. wojciech-lipce": "Orunia-Św. Wojciech-Lipce",
    "orunia-sw. wojciech-lipce": "Orunia-Św. Wojciech-Lipce",
    "ujeścisko-łostowice": "Ujeścisko-Łostowice",
    "ujescisko-lostowice": "Ujeścisko-Łostowice",
    "pustki cisowskie-demptowo": "Pustki Cisowskie-Demptowo",
}

DISTRICT_CITY = {
    "Aniołki": "Gdańsk",
    "Brzeźno": "Gdańsk",
    "Brętowo": "Gdańsk",
    "Chełm": "Gdańsk",
    "Jasień": "Gdańsk",
    "Letnica": "Gdańsk",
    "Morena": "Gdańsk",
    "Oliwa": "Gdańsk",
    "Orunia": "Gdańsk",
    "Orunia-Św. Wojciech-Lipce": "Gdańsk",
    "Piecki-Migowo": "Gdańsk",
    "Przymorze": "Gdańsk",
    "Śródmieście": "Gdańsk",
    "Ujeścisko": "Gdańsk",
    "Ujeścisko-Łostowice": "Gdańsk",
    "Wrzeszcz": "Gdańsk",
    "Zaspa": "Gdańsk",
    "Żabianka": "Gdańsk",
    "Karwiny": "Gdynia",
    "Mały Kack": "Gdynia",
    "Orłowo": "Gdynia",
    "Pustki Cisowskie-Demptowo": "Gdynia",
    "Redłowo": "Gdynia",
    "Witomino": "Gdynia",
    "Dolny Sopot": "Sopot",
    "Górny Sopot": "Sopot",
}


def _location_key(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().casefold()).strip(" ,")


def normalize_location(
    city: str | None,
    district: str | None,
    street: str | None,
) -> tuple[str | None, str | None, str | None]:
    city_key = _location_key(city)
    district_key = _location_key(district)
    street_key = _location_key(street)

    normalized_city = KNOWN_CITIES.get(city_key) or (city.strip(" ,") if city else None)
    normalized_district = KNOWN_DISTRICTS.get(district_key) or (
        district.strip(" ,") if district else None
    )
    normalized_street = street.strip(" ,") if street else None

    if city_key in KNOWN_DISTRICTS:
        normalized_district = KNOWN_DISTRICTS[city_key]
        normalized_city = DISTRICT_CITY.get(normalized_district, normalized_city)
    if district_key in KNOWN_CITIES:
        normalized_city = KNOWN_CITIES[district_key]
        normalized_district = None
    if street_key in KNOWN_CITIES:
        normalized_city = KNOWN_CITIES[street_key]
        normalized_street = None
    if street_key in KNOWN_DISTRICTS:
        normalized_district = normalized_district or KNOWN_DISTRICTS[street_key]
        normalized_street = None

    if normalized_district in DISTRICT_CITY and normalized_city not in KNOWN_CITIES.values():
        normalized_city = DISTRICT_CITY[normalized_district]

    if (
        district_key
        and district_key not in KNOWN_DISTRICTS
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
