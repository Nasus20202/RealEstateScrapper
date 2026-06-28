"""Nieruchomosci-online.pl scraper — parses listing data from DOM via selectolax."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import looks_like_street_or_code
from realestate.scrapers.images import looks_like_listing_image, unique_listing_images

_BASE_URL = "https://www.nieruchomosci-online.pl"
_KNOWN_CITIES = ("Gdańsk", "Gdynia", "Sopot", "Rumia", "Reda", "Wejherowo")
_PROVINCES = {
    "dolnośląskie",
    "kujawsko-pomorskie",
    "lubelskie",
    "lubuskie",
    "łódzkie",
    "małopolskie",
    "mazowieckie",
    "opolskie",
    "podkarpackie",
    "podlaskie",
    "pomorskie",
    "śląskie",
    "świętokrzyskie",
    "warmińsko-mazurskie",
    "wielkopolskie",
    "zachodniopomorskie",
}

# Tile container selector — every listing card has a data-id attribute
_TILE_SEL = ".tile[data-id]"


def _money(text: str | None) -> Decimal | None:
    """Parse a Polish price string like '568\xa0292\xa0zł' into a Decimal."""
    if not text:
        return None
    # Strip non-breaking spaces and regular spaces first
    cleaned = text.replace("\xa0", "").replace(" ", "")
    # Keep only digits and commas; drop dots (thousands separators)
    cleaned = re.sub(r"[^\d,]", "", cleaned)
    # Polish decimal separator is comma; replace with dot for parsing
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation, ValueError:
        return None


def _area(text: str | None) -> float | None:
    """Parse a Polish area string like '32,58\xa0m²' into a float."""
    if not text:
        return None
    cleaned = text.replace("\xa0", "").replace(" ", "").replace("m²", "").replace("m2", "").strip()
    # Keep only digits and commas; drop dots (thousands separators)
    cleaned = re.sub(r"[^\d,]", "", cleaned)
    # Polish decimal separator is comma; replace with dot for parsing
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError, TypeError:
        return None


def _external_id(url: str) -> str:
    """Extract the numeric offer ID from a nieruchomosci-online URL."""
    match = re.search(r"/(\d+)\.html", url)
    if match:
        return match.group(1)
    # Fallback: use the full URL
    return url


def _absolute_url(href: str) -> str:
    """Ensure the URL is absolute; prepend _BASE_URL if relative."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return _BASE_URL + href


def _image_url(node) -> str:
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        value = node.attrs.get(attr, "")
        if value:
            return _absolute_url(value)
    srcset = node.attrs.get("srcset", "")
    if srcset:
        return _absolute_url(srcset.split(",")[0].strip().split(" ")[0])
    return ""


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip(" ,")
    return cleaned or None


def _split_address(text: str | None) -> tuple[str | None, str | None, str | None]:
    cleaned = _clean_text(text)
    if not cleaned:
        return None, None, None
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    city = district = street = None
    if len(parts) >= 3:
        street = parts[0]
        district = parts[-2]
        city = parts[-1]
    elif len(parts) == 2:
        first, second = parts
        if second.casefold() in _PROVINCES:
            city = first
        elif any(second.lower() == city.lower() for city in _KNOWN_CITIES):
            district, city = first, second
        else:
            street, city = first, second
    else:
        for known_city in _KNOWN_CITIES:
            suffix = f" {known_city}".lower()
            if parts[0].lower().endswith(suffix):
                city = known_city
                district = parts[0][: -len(known_city)].strip(" ,") or None
                break
        if city is None:
            city = parts[0]
    return _sanitize_address(city, district, street)


def _sanitize_address(
    city: str | None,
    district: str | None,
    street: str | None,
) -> tuple[str | None, str | None, str | None]:
    if looks_like_street_or_code(district):
        street = street or district
        district = None
    return city, district, street


def _json_ld_address(tree: HTMLParser) -> tuple[str | None, str | None, str | None]:
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if item_type in {"Organization", "LocalBusiness", "RealEstateAgent"}:
                continue
            address = item.get("address")
            if not isinstance(address, dict):
                continue
            city = _clean_text(address.get("addressLocality"))
            street = _clean_text(address.get("streetAddress"))
            district = _clean_text(address.get("addressRegion"))
            return _sanitize_address(city, district, street)
    return None, None, None


def _street_from_title(title: str | None) -> str | None:
    if not title:
        return None
    match = re.search(
        r"\b((?:ul\.|ulica|aleja|al\.)\s+[^,|]+)",
        title,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    street = _clean_text(match.group(1))
    if not street:
        return None
    return re.sub(r"^ulica\s+", "ul. ", street, flags=re.IGNORECASE)


def _json_ld_detail(tree: HTMLParser) -> dict:
    detail: dict = {}
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if not isinstance(item, dict):
                continue
            if item.get("description") and not detail.get("description"):
                detail["description"] = item.get("description")
            geo = item.get("geo")
            if isinstance(geo, dict):
                detail["lat"] = _float(geo.get("latitude"))
                detail["lon"] = _float(geo.get("longitude"))
    return detail


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError, TypeError:
        return None


def _meta_content(tree: HTMLParser, *selectors: str) -> str | None:
    for selector in selectors:
        node = tree.css_first(selector)
        value = node.attrs.get("content") if node else None
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _detail_description(tree: HTMLParser) -> str | None:
    selectors = [
        ".description",
        "#description",
        ".offer-description",
        '[itemprop="description"]',
        '[class*="description"]',
        '[class*="Description"]',
    ]
    for selector in selectors:
        node = tree.css_first(selector)
        if node:
            raw = node.html or node.text()
            if _clean_text(node.text()):
                return raw
    json_detail = _json_ld_detail(tree)
    if json_detail.get("description"):
        return str(json_detail["description"])
    return _meta_content(
        tree,
        'meta[property="og:description"]',
        'meta[name="description"]',
    )


def _detail_coordinates(tree: HTMLParser) -> tuple[float | None, float | None]:
    json_detail = _json_ld_detail(tree)
    lat = json_detail.get("lat")
    lon = json_detail.get("lon")
    if lat is not None and lon is not None:
        return lat, lon
    lat = _float(_meta_content(tree, 'meta[property="place:location:latitude"]'))
    lon = _float(_meta_content(tree, 'meta[property="place:location:longitude"]'))
    if lat is not None and lon is not None:
        return lat, lon
    html = tree.html or ""
    match = re.search(r'"latitude"\s*:\s*"?([0-9.,-]+)"?.*?"longitude"\s*:\s*"?([0-9.,-]+)"?', html)
    if match:
        return _float(match.group(1)), _float(match.group(2))
    return None, None


def _detail_address(tree: HTMLParser) -> tuple[str | None, str | None, str | None]:
    city, district, street = _json_ld_address(tree)
    if city or district or street:
        return city, district, street

    selectors = [
        "[data-address]",
        '[itemprop="address"]',
        '[itemprop="streetAddress"]',
        '[data-testid*="address"]',
        '[class*="address"]',
        '[class*="location"]',
        '[class*="Localization"]',
        ".offer__location",
        ".summary__location",
        ".parameters__location",
    ]
    for selector in selectors:
        node = tree.css_first(selector)
        if node:
            parsed = _split_address(node.attrs.get("data-address") or node.text())
            if any(parsed):
                return parsed
    return None, None, None


def _parse_rooms(tile: object) -> int | None:
    """Extract rooms count from .attributes__box--item containing 'pokoi'."""
    for item in tile.css(".attributes__box--item"):  # type: ignore[attr-defined]
        p = item.css_first("p")
        if p and "pokoi" in p.text().lower():
            strong = item.css_first("strong")
            if strong:
                try:
                    return int(strong.text().strip())
                except ValueError, TypeError:
                    return None
    return None


def _parse_floor(tile: object) -> int | None:
    """Extract floor number from .attributes__box--item containing 'piętro'."""
    for item in tile.css(".attributes__box--item"):  # type: ignore[attr-defined]
        p = item.css_first("p")
        if p and "piętro" in p.text().lower():
            strongs = item.css("strong")
            if strongs:
                try:
                    return int(strongs[0].text().strip())
                except ValueError, TypeError:
                    return None
    return None


class NieruchomosciOnlineScraper:
    source_id = "nieruchomosci-online"
    display_name = "Nieruchomości-online"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build a nieruchomosci-online.pl search URL for the given criteria."""
        city = criteria.city.capitalize()
        url = f"{_BASE_URL}/szukaj.html?3,mieszkanie,sprzedaz,,{city}"
        if page > 1:
            url += f"&p={page}"
        return url

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse a nieruchomosci-online.pl search results page and return RawListings."""
        tree = HTMLParser(html)
        tiles = tree.css(_TILE_SEL)
        listings: list[RawListing] = []

        for tile in tiles:
            # --- URL and title ---
            h2_link = tile.css_first("h2 a")
            if h2_link is None:
                continue
            raw_href = h2_link.attrs.get("href", "")
            url = _absolute_url(raw_href)
            if not url:
                continue
            title = h2_link.text().strip()
            external_id = _external_id(url)

            # --- Price and area ---
            # .primary-display spans: [0] price, [1] area, [2] price/m²
            primary = tile.css_first(".primary-display")
            price: Decimal | None = None
            area_m2: float | None = None
            if primary:
                spans = primary.css("span")
                if spans:
                    price = _money(spans[0].text())
                if len(spans) > 1:
                    area_m2 = _area(spans[1].text())

            # --- Rooms and floor ---
            rooms = _parse_rooms(tile)
            floor = _parse_floor(tile)

            # --- Location ---
            city_str: str | None = None
            district: str | None = None
            province = tile.css_first(".province")
            if province:
                city_str, district, _street = _split_address(province.text())

            # --- Market type ---
            market_type = tile.attrs.get("data-market-type")
            market: str | None = None
            if market_type == "primary":
                market = "primary"
            elif market_type == "secondary":
                market = "secondary"

            # --- Thumbnail image ---
            images: list[str] = []
            for img_el in tile.css("img"):
                src = _image_url(img_el)
                if src and looks_like_listing_image(src) and src not in images:
                    images.append(src)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=external_id,
                    url=url,
                    title=title,
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor,
                    city=city_str,
                    district=district,
                    market=market,
                    images=unique_listing_images(images),
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse a nieruchomosci-online.pl detail page; returns a minimal RawListing."""
        external_id = _external_id(url)
        tree = HTMLParser(html)

        # Title
        h1 = tree.css_first("h1")
        title = h1.text().strip() if h1 else ""

        description = _detail_description(tree)

        city, district, street = _detail_address(tree)
        title_street = _street_from_title(title)
        if title_street:
            street = title_street
        lat, lon = _detail_coordinates(tree)

        # Images
        images: list[str] = []
        for img in tree.css("img, .gallery [data-src], [data-gallery] img"):
            src = _image_url(img)
            if src and looks_like_listing_image(src) and src not in images:
                images.append(src)

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=title,
            description=description,
            city=city,
            district=district,
            street=street,
            lat=lat,
            lon=lon,
            images=unique_listing_images(images),
        )


register(NieruchomosciOnlineScraper())
