"""RynekPierwotny.pl scraper — parses __INITIAL_STATE__ JSON for investment listings."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://rynekpierwotny.pl"

_CITY_SLUGS: dict[str, str] = {
    "gdansk": "gdansk",
    "gdynia": "gdynia",
    "sopot": "sopot",
}

_CITY_DISPLAY: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
}


def _slugify_city(city: str) -> str:
    city = city.strip().lower().replace("ł", "l")
    folded = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "-", folded.strip())


def _city_from_address(address: str) -> str | None:
    for display in _CITY_DISPLAY.values():
        if display.lower() in address.lower():
            return display
    return None


def _district_from_address(address: str, city: str | None) -> str | None:
    if not city:
        return None
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        district = parts[1].strip()
        if district and district.lower() != city.lower():
            return district
    return None


def _street_from_address(address: str) -> str | None:
    parts = [p.strip() for p in address.split(",")]
    for part in parts:
        if part and re.search(r"(ul\.|al\.|pl\.|os\.)", part, re.IGNORECASE):
            return part
    return None


def _money(value: object) -> Decimal | None:
    if value in (None, 0, 0.0, "0", "0.0"):
        return None
    try:
        v = Decimal(str(value))
        return v if v > 0 else None
    except InvalidOperation, ValueError, TypeError:
        return None


def _float(value: object) -> float | None:
    if value in (None, 0, 0.0, "0", "0.0"):
        return None
    try:
        v = float(str(value).replace(",", "."))
        return v if v > 0 else None
    except TypeError, ValueError:
        return None


def _int(value: object) -> int | None:
    if value in (None, 0, 0.0, "0"):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _extract_initial_state(html: str) -> dict:
    match = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});",
        html,
        re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _build_investment_url(offer: dict) -> str:
    vendor = offer.get("vendor") or {}
    vendor_slug = vendor.get("slug") or ""
    offer_slug = offer.get("slug") or ""
    offer_id = offer.get("id") or ""
    return f"{_BASE_URL}/oferty/{vendor_slug}/{offer_slug}-{offer_id}/"


def _extract_images(offer: dict) -> list[str]:
    urls: list[str] = []
    main_img = offer.get("main_image") or {}
    for key in ("m_img_500", "m_img_750", "m_img_375x211"):
        url = main_img.get(key)
        if url and isinstance(url, str):
            urls.append(url)
            break
    gallery = offer.get("gallery") or []
    for item in gallery[:5]:
        if isinstance(item, dict):
            url = item.get("m_img_500") or item.get("m_img_375x211") or ""
            if url:
                urls.append(url)
        elif isinstance(item, str):
            urls.append(item)
    return unique_listing_images(urls)


def _parse_offer(offer: dict) -> RawListing | None:
    offer_id = offer.get("id")
    if offer_id is None:
        return None

    name = offer.get("name") or ""
    address = offer.get("address") or ""
    description = offer.get("description") or ""

    city = _city_from_address(address)
    district = _district_from_address(address, city)
    street = _street_from_address(address)

    stats = offer.get("stats") or {}
    price_min = _money(stats.get("ranges_price_min"))
    price_max = _money(stats.get("ranges_price_max"))
    area_min = _float(stats.get("ranges_area_min"))
    area_max = _float(stats.get("ranges_area_max"))
    rooms_min = _int(stats.get("ranges_rooms_min"))
    rooms_max = _int(stats.get("ranges_rooms_max"))

    geo = offer.get("geo_point") or {}
    coords = geo.get("coordinates") or []
    lon = _float(coords[0]) if len(coords) >= 2 else None
    lat = _float(coords[1]) if len(coords) >= 2 else None

    vendor = offer.get("vendor") or {}
    vendor_name = vendor.get("name") or ""

    url = _build_investment_url(offer)
    images = _extract_images(offer)

    properties_count = stats.get("properties_count_for_sale") or 0

    price_text = ""
    if price_min and price_max:
        price_text = f"od {price_min:,.0f} zł".replace(",", " ")
    elif price_min:
        price_text = f"od {price_min:,.0f} zł".replace(",", " ")

    title_parts = [name]
    if price_text:
        title_parts.append(price_text)
    title = " — ".join(title_parts)

    attributes: dict = {
        "investment_name": name,
        "developer": vendor_name,
        "address": address,
        "available_properties": properties_count,
    }
    if price_min and price_max:
        attributes["price_range"] = f"{price_min}-{price_max}"
    elif price_min:
        attributes["price_from"] = price_min
    if area_min and area_max:
        attributes["area_range"] = f"{area_min}-{area_max}"
    if rooms_min and rooms_max:
        attributes["rooms_range"] = f"{rooms_min}-{rooms_max}"

    construction = offer.get("construction_date_range") or {}
    completion_upper = construction.get("upper")
    if completion_upper:
        attributes["completion_date"] = completion_upper

    has_promotions = offer.get("has_active_promotions") or False
    if has_promotions:
        attributes["has_promotions"] = True

    is_condohotel = offer.get("is_condohotel") or False
    if is_condohotel:
        attributes["is_condohotel"] = True

    return RawListing(
        source_id="rynekpierwotny",
        external_id=str(offer_id),
        url=url,
        title=title,
        price=price_min,
        area_m2=area_min,
        rooms=rooms_min,
        city=city,
        district=district,
        street=street,
        lat=lat,
        lon=lon,
        market="primary",
        description=description if description else None,
        attributes=attributes,
        images=images,
    )


class RynekPierwotnyScraper:
    source_id = "rynekpierwotny"
    display_name = "RynekPierwotny"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        city_slug = _slugify_city(criteria.city)
        url = f"{_BASE_URL}/s/nowe-mieszkania-{city_slug}/"
        if page > 1:
            url += f"?page={page}"
        return url

    def parse_search(self, html: str) -> list[RawListing]:
        state = _extract_initial_state(html)
        offers = state.get("offerList", {}).get("list", {}).get("offers", [])
        listings: list[RawListing] = []
        seen_ids: set[str] = set()
        for offer in offers:
            listing = _parse_offer(offer)
            if listing is None:
                continue
            if listing.external_id in seen_ids:
                continue
            seen_ids.add(listing.external_id)
            listings.append(listing)
        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        tree = HTMLParser(html)
        h1 = tree.css_first("h1")
        title = h1.text(strip=True) if h1 else ""
        if not title:
            t = tree.css_first("title")
            title = t.text(strip=True) if t else ""

        state = _extract_initial_state(html)
        offer_data = state.get("offerDetail", {}).get("offer") or {}
        if isinstance(offer_data, dict) and offer_data.get("id"):
            listing = _parse_offer(offer_data)
            if listing:
                listing.url = url
                return listing

        desc_el = tree.css_first(".description, .content, article")
        description: str | None = None
        if desc_el:
            raw = desc_el.text(strip=True)
            description = raw if raw else None

        images: list[str] = []
        for img in tree.css("img[src]"):
            src = img.attributes.get("src", "")
            if src and "rynekpierwotny.pl" in src and src not in images:
                images.append(src)

        slug = url.rstrip("/").split("/")[-1]
        ext_id = slug

        return RawListing(
            source_id="rynekpierwotny",
            external_id=ext_id,
            url=url,
            title=title,
            description=description,
            images=unique_listing_images(images),
            market="primary",
        )


register(RynekPierwotnyScraper())
