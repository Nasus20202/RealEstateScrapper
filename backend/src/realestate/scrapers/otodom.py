"""Otodom.pl scraper — parses listing data from __NEXT_DATA__ JSON."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urljoin

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.images import unique_listing_images


def _slugify_city(city: str) -> str:
    """ASCII-fold a Polish city name into an otodom URL slug.

    Otodom location slugs are ASCII (e.g. "gdansk"). A diacritic slug such as
    "gdańsk" makes otodom 301-redirect to /cala-polska?fromInvalidLocation=true
    (all of Poland), silently breaking the city filter. ``ł`` has no Unicode
    decomposition, so map it explicitly before NFKD folding.
    """
    city = city.strip().lower().replace("ł", "l")
    folded = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "-", folded.strip())


_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)

# Otodom string enum → int mapping for roomsNumber
_ROOMS_MAP: dict[str, int] = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
}

# Otodom floor enum → int mapping
_FLOOR_MAP: dict[str, int] = {
    "GROUND": 0,
    "FIRST": 1,
    "SECOND": 2,
    "THIRD": 3,
    "FOURTH": 4,
    "FIFTH": 5,
    "SIXTH": 6,
    "SEVENTH": 7,
    "EIGHTH": 8,
    "NINTH": 9,
    "TENTH": 10,
    "ABOVE_TENTH": 11,
}

_BASE_URL = "https://www.otodom.pl"
_LISTING_LINK_RE = re.compile(
    r'<a[^>]+href="(?P<href>(?:https://www\.otodom\.pl)?/pl/oferta/(?P<slug>[^"?#]+))"[^>]*>(?P<body>.*?)</a>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _parse_dt(v: object) -> datetime | None:
    """Defensively parse a dateCreated string like '2026-06-21 16:37:27' into datetime."""
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def _extract_next_data(html: str) -> dict:
    """Extract and parse __NEXT_DATA__ JSON from HTML."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError, ValueError:
        return {}


def _extract_images(item: dict) -> list[str]:
    """Extract image URLs from an item dict, preferring 'large' then 'medium' then 'url'."""
    images_raw = item.get("images") or item.get("photos") or []
    urls: list[str] = []
    for img in images_raw:
        if not isinstance(img, dict):
            continue
        url = img.get("large") or img.get("medium") or img.get("url")
        if url and isinstance(url, str):
            urls.append(url)
    return unique_listing_images(urls)


def _extract_attributes(item: dict) -> dict:
    attrs: dict = {}
    tags = item.get("tags") or []
    if isinstance(tags, list):
        values = [tag.get("value") for tag in tags if isinstance(tag, dict) and tag.get("value")]
        if values:
            attrs["tags"] = values
    if item.get("isPrivateOwner") is not None:
        attrs["private_owner"] = bool(item.get("isPrivateOwner"))
    if item.get("isExclusiveOffer") is not None:
        attrs["exclusive"] = bool(item.get("isExclusiveOffer"))
    return attrs


def _extract_district(item: dict) -> str | None:
    """Extract district from reverseGeocoding locations."""
    location = item.get("location")
    if not isinstance(location, dict):
        return None
    reverse_geo = location.get("reverseGeocoding") or {}
    locations = reverse_geo.get("locations") or []
    for loc in locations:
        if isinstance(loc, dict) and loc.get("locationLevel") == "district":
            return loc.get("name")
    return None


def _extract_price(item: dict) -> Decimal | None:
    """Extract price as Decimal; return None if hidden or absent."""
    if item.get("hidePrice"):
        return None
    total_price = item.get("totalPrice")
    if isinstance(total_price, dict):
        value = total_price.get("value")
    else:
        # fallback: try a top-level numeric price field
        value = item.get("price")

    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation, TypeError:
        return None


def _extract_rooms(item: dict) -> int | None:
    """Map roomsNumber enum or int to int; return None when not mappable."""
    rooms_raw = item.get("roomsNumber")
    if rooms_raw is None:
        return None
    if isinstance(rooms_raw, int):
        return rooms_raw
    if isinstance(rooms_raw, str):
        return _ROOMS_MAP.get(rooms_raw.upper())
    return None


def _extract_floor(item: dict) -> int | None:
    """Map floorNumber enum or int to int; return None when not mappable."""
    floor_raw = item.get("floorNumber")
    if floor_raw is None:
        return None
    if isinstance(floor_raw, int):
        return floor_raw
    if isinstance(floor_raw, str):
        # Try direct int cast first, then enum map
        try:
            return int(floor_raw)
        except ValueError:
            return _FLOOR_MAP.get(floor_raw.upper())
    return None


def _build_url(item: dict) -> str:
    """Build absolute listing URL from slug or href."""
    slug = item.get("slug")
    if slug:
        return f"{_BASE_URL}/pl/oferta/{slug}"
    href = item.get("href") or ""
    if href.startswith("http"):
        return href
    # href may be like "[lang]/ad/..." — replace [lang] with /pl
    href = re.sub(r"^\[lang\]", "/pl", href)
    return urljoin(_BASE_URL, href)


def _text_from_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _parse_listing_links(html: str) -> list[RawListing]:
    """Fallback for rendered Otodom pages when structured JSON is missing."""
    listings: list[RawListing] = []
    seen: set[str] = set()
    for match in _LISTING_LINK_RE.finditer(html):
        slug = match.group("slug")
        if slug in seen:
            continue
        seen.add(slug)
        title = _text_from_html(match.group("body"))
        listings.append(
            RawListing(
                source_id=OtodomScraper.source_id,
                external_id=slug.rsplit("-", 1)[-1],
                url=urljoin(_BASE_URL, match.group("href")),
                title=title or slug.replace("-", " "),
            )
        )
    return listings


def _listing_from_item(source_id: str, item: dict) -> RawListing | None:
    item_id = item.get("id")
    if item_id is None:
        return None

    return RawListing(
        source_id=source_id,
        external_id=str(item_id),
        url=_build_url(item),
        title=item.get("title") or "",
        price=_extract_price(item),
        area_m2=item.get("areaInSquareMeters"),
        rooms=_extract_rooms(item),
        floor=_extract_floor(item),
        city=((item.get("location") or {}).get("address", {}).get("city", {}).get("name")),
        district=_extract_district(item),
        market=_map_market(item),
        description=item.get("shortDescription"),
        attributes=_extract_attributes(item),
        posted_at=_parse_dt(item.get("dateCreated")),
        images=_extract_images(item),
        raw=item,
    )


def _map_market(item: dict) -> str | None:
    """Map transaction/market to 'primary'/'secondary'; None if unknown.

    Heuristic (best-effort, not authoritative):
      - source URN contains "obido"  → primary market (developer via Obido)
      - source present but not obido → secondary market (agency/partner partner)
      - source absent/None           → None (cannot determine)

    Falls back to an explicit 'market' key when present (future-proofing).
    """
    # Check for an explicit 'market' key first (future-proofing)
    market_raw = item.get("market")
    if isinstance(market_raw, str):
        m = market_raw.lower()
        if m in ("primary", "pierwotny", "primary_market"):
            return "primary"
        if m in ("secondary", "wtorny", "secondary_market"):
            return "secondary"

    # Infer from 'source' URN
    source = item.get("source")
    if isinstance(source, str) and source:
        if "obido" in source.lower():
            return "primary"
        # Any other non-empty partner/site source → secondary market
        return "secondary"

    return None


class OtodomScraper:
    source_id = "otodom"
    display_name = "Otodom"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build an Otodom search URL for the given criteria and page number."""
        city = _slugify_city(criteria.city)
        base = f"{_BASE_URL}/pl/wyniki/sprzedaz/mieszkanie/pomorskie/{city}"
        params: dict[str, str | int] = {"page": page}
        if criteria.min_price is not None:
            params["priceMin"] = criteria.min_price
        if criteria.max_price is not None:
            params["priceMax"] = criteria.max_price
        if criteria.min_area is not None:
            params["areaMin"] = criteria.min_area
        if criteria.max_area is not None:
            params["areaMax"] = criteria.max_area
        if criteria.min_rooms is not None:
            params["roomsNumber"] = criteria.min_rooms
        return f"{base}?{urlencode(params)}"

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse an Otodom search results page and return a list of RawListing."""
        data = _extract_next_data(html)
        items = (
            data.get("props", {})
            .get("pageProps", {})
            .get("data", {})
            .get("searchAds", {})
            .get("items", [])
        )

        if not items:
            return _parse_listing_links(html)

        listings: list[RawListing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            related_ads = item.get("relatedAds") or []
            item_group = related_ads if related_ads else [item]
            for grouped_item in item_group:
                if not isinstance(grouped_item, dict):
                    continue
                listing = _listing_from_item(self.source_id, grouped_item)
                if listing is not None:
                    listings.append(listing)
        return listings

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse an Otodom detail page; returns a RawListing (defensively)."""
        data = _extract_next_data(html)
        ad = data.get("props", {}).get("pageProps", {}).get("ad", {})

        # Extract id from URL as fallback
        slug_match = re.search(r"/oferta/([^/?#]+)", url)
        external_id = slug_match.group(1) if slug_match else url

        if not isinstance(ad, dict) or not ad:
            return RawListing(
                source_id=self.source_id,
                external_id=external_id,
                url=url,
                title="",
            )

        item_id = ad.get("id")
        if item_id:
            external_id = str(item_id)

        location = ad.get("location") or {}
        address = location.get("address") or {}

        # District from reverseGeocoding
        district = _extract_district(ad)

        # Street
        street_data = address.get("street") or {}
        street = street_data.get("name")

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=ad.get("title") or "",
            price=_extract_price(ad),
            area_m2=ad.get("areaInSquareMeters"),
            rooms=_extract_rooms(ad),
            floor=_extract_floor(ad),
            city=(address.get("city") or {}).get("name"),
            district=district,
            street=street,
            market=_map_market(ad),
            description=ad.get("description"),
            attributes=_extract_attributes(ad),
            images=_extract_images(ad),
            raw=ad,
        )


register(OtodomScraper())
