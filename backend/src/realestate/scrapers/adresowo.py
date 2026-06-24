"""Adresowo.pl scraper — parses listing data from DOM via selectolax."""

from __future__ import annotations

import re
from decimal import Decimal

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import (
    absolute_url,
    image_url,
    parse_area,
    parse_int_text,
    parse_money,
    slugify_city,
)
from realestate.scrapers.images import looks_like_listing_image, unique_listing_images

_BASE_URL = "https://adresowo.pl"
_TRICITY_CITIES = ("gdansk", "gdynia", "sopot")


def _external_id(url: str) -> str:
    """Extract the offer slug/ID from an adresowo URL."""
    match = re.search(r"-([a-z0-9]+)$", url.rstrip("/"))
    if match:
        return match.group(1)
    return url


def _geo_script(tree: HTMLParser) -> dict:
    """Extract re.geo.* values from inline JavaScript."""
    for script in tree.css("script"):
        raw = script.text(strip=True)
        if "re.geo" not in raw:
            continue
        geo: dict = {}
        for match in re.finditer(r"re\.geo\.(\w+)\s*=\s*'?([^';\n]+)'?", raw):
            key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            geo[key] = value
        return geo
    return {}


def _parse_detail_url_id(url: str) -> str:
    """Extract the alphanumeric ID at the end of the URL slug."""
    match = re.search(r"/o/[^/]+-([a-z0-9]+)$", url.rstrip("/"))
    if match:
        return match.group(1)
    return _external_id(url)


class AdresowoScraper:
    source_id = "adresowo"
    display_name = "Adresowo"

    def __init__(self) -> None:
        self._last_city_slug: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build an adresowo.pl search URL for the given criteria.

        For Trójmiasto we generate URLs for Gdańsk (primary); Gdynia and Sopot
        can be added as separate pages if needed.
        """
        city_slug = slugify_city(criteria.city)
        self._last_city_slug = city_slug
        base = f"{_BASE_URL}/mieszkania/{city_slug}/"
        if page > 1:
            base += f"_l{page}"
        return base

    def _build_tricity_urls(self, page: int = 1) -> list[str]:
        """Build search URLs for all Tricity cities."""
        return [
            f"{_BASE_URL}/mieszkania/{city}/" + (f"_l{page}" if page > 1 else "")
            for city in _TRICITY_CITIES
        ]

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse an adresowo.pl search results page and return RawListings."""
        tree = HTMLParser(html)
        tiles = tree.css("[data-offer-card]")
        listings: list[RawListing] = []

        for tile in tiles:
            data_id = tile.attrs.get("data-id", "")

            # --- URL and title ---
            h2_link = tile.css_first("h2 a")
            if h2_link is None:
                continue
            raw_href = h2_link.attrs.get("href", "")
            url = absolute_url(raw_href, _BASE_URL)
            if not url:
                continue

            # Extract location and type from the link spans
            bold_span = h2_link.css_first("span.font-bold")
            location_text = bold_span.text().strip() if bold_span else ""
            street_span = h2_link.css_first("span.text-neutral-900:not(.font-bold)")
            street_text = street_span.text().strip() if street_span else ""

            title = f"{location_text} {street_text}".strip()

            external_id = data_id or _external_id(url)

            # --- Price, area, rooms ---
            price: Decimal | None = None
            area_m2: float | None = None
            rooms: int | None = None

            # The card has three price/area/rooms blocks in the top row
            bold_spans = tile.css(".flex .font-bold")
            for span in bold_spans:
                parent_p = span.parent
                if parent_p is None:
                    continue
                text_after = parent_p.text()
                if "zł" in text_after and price is None:
                    price = parse_money(span.text() + " zł")
                elif "m²" in text_after and area_m2 is None:
                    area_m2 = parse_area(span.text())
                elif "pok" in text_after and rooms is None:
                    rooms = parse_int_text(span.text())

            # --- Location details ---
            city_str: str | None = None
            district: str | None = None
            # location_text often has "Gdańsk Oliwa" or "Warszawa Wola"
            if location_text:
                parts = location_text.split()
                if len(parts) >= 2:
                    city_str = parts[0]
                    district = " ".join(parts[1:])
                elif parts:
                    city_str = parts[0]

            if self._last_city_slug and city_str and slugify_city(city_str) != self._last_city_slug:
                continue

            # --- Images ---
            images: list[str] = []
            for img in tile.css("img"):
                src = image_url(img, _BASE_URL)
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
                    city=city_str,
                    district=district,
                    street=street_text or None,
                    images=unique_listing_images(images),
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse an adresowo.pl detail page; returns a RawListing."""
        external_id = _parse_detail_url_id(url)
        tree = HTMLParser(html)

        # --- Title from og:title ---
        title = ""
        og_title = tree.css_first('meta[property="og:title"]')
        if og_title:
            title = og_title.attrs.get("content", "")

        # --- Description from og:description ---
        description = ""
        og_desc = tree.css_first('meta[property="og:description"]')
        if og_desc:
            description = og_desc.attrs.get("content", "")

        # --- Geo data from inline JS ---
        geo = _geo_script(tree)
        city_str = geo.get("city")
        district = geo.get("district")
        street = geo.get("street")
        building_number = geo.get("buildingNumber")
        if street and building_number and geo.get("showBuildingNumber") == "1":
            street = f"{street} {building_number}"

        lat = None
        lng = None
        if geo.get("lat"):
            try:
                lat = float(geo["lat"])
            except ValueError, TypeError:
                pass
        if geo.get("lng"):
            try:
                lng = float(geo["lng"])
            except ValueError, TypeError:
                pass

        # --- Images from re.offerImages JS dict ---
        images: list[str] = []
        for script in tree.css("script"):
            raw = script.text(strip=True)
            if "re.offerImages" not in raw:
                continue
            for img_match in re.finditer(r"'(https?://[^']+)'", raw):
                img_url = img_match.group(1)
                if looks_like_listing_image(img_url) and img_url not in images:
                    images.append(img_url)
            break

        # --- Price, area, rooms from header stats ---
        price: Decimal | None = None
        area_m2: float | None = None
        rooms: int | None = None
        floor: int | None = None

        # Extract price and area from og:title
        if title:
            area_match = re.search(r"(\d+(?:[,\.]\d+)?)\s*m[²2]", title)
            if area_match:
                area_m2 = parse_area(area_match.group(1) + " m²")
            price_match = re.search(r"([\d\xa0 ]+)\s*zł\s*$", title)
            if price_match:
                price = parse_money(price_match.group(1) + " zł")

        # Try to extract from page text: "3 pokoje", "2 piętro"
        page_text = tree.html or ""
        rooms_match = re.search(r"(\d+)\s*poko[ji]", page_text)
        if rooms_match:
            rooms = parse_int_text(rooms_match.group(1))
        floor_match = re.search(r"(\d+)\s*piętro", page_text)
        if floor_match:
            floor = parse_int_text(floor_match.group(1))

        return RawListing(
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
            street=street,
            lat=lat,
            lon=lng,
            description=description or None,
            images=unique_listing_images(images),
        )


register(AdresowoScraper())
