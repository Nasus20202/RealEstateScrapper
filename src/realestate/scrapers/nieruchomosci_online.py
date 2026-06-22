"""Nieruchomosci-online.pl scraper — parses listing data from DOM via selectolax."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register

_BASE_URL = "https://www.nieruchomosci-online.pl"

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
    except (InvalidOperation, ValueError):
        return None


def _area(text: str | None) -> float | None:
    """Parse a Polish area string like '32,58\xa0m²' into a float."""
    if not text:
        return None
    cleaned = (
        text.replace("\xa0", "")
        .replace(" ", "")
        .replace("m²", "")
        .replace("m2", "")
        .strip()
    )
    # Keep only digits and commas; drop dots (thousands separators)
    cleaned = re.sub(r"[^\d,]", "", cleaned)
    # Polish decimal separator is comma; replace with dot for parsing
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
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


def _parse_rooms(tile: object) -> int | None:
    """Extract rooms count from .attributes__box--item containing 'pokoi'."""
    for item in tile.css(".attributes__box--item"):  # type: ignore[attr-defined]
        p = item.css_first("p")
        if p and "pokoi" in p.text().lower():
            strong = item.css_first("strong")
            if strong:
                try:
                    return int(strong.text().strip())
                except (ValueError, TypeError):
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
                except (ValueError, TypeError):
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
                prov_text = province.text().strip()
                # Province text is like "Dzielnica,Miasto" or "Dzielnica Miasto"
                # Last word/part is typically the city (Gdańsk)
                parts = re.split(r"[,\s]+", prov_text)
                parts = [p.strip() for p in parts if p.strip()]
                if parts:
                    city_str = parts[-1]
                    if len(parts) > 1:
                        district = parts[0]

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
                if src and src not in images:
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
                    images=images,
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

        # Description
        desc_el = tree.css_first(".description, #description, .offer-description")
        description = desc_el.text().strip() if desc_el else None

        # Images
        images: list[str] = []
        for img in tree.css("img, .gallery [data-src], [data-gallery] img"):
            src = _image_url(img)
            if src and src not in images:
                images.append(src)

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=title,
            description=description,
            images=images,
        )


register(NieruchomosciOnlineScraper())
