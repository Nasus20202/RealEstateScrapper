"""Morizon.pl scraper — parses listing data from DOM via selectolax."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import looks_like_street_or_code
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.morizon.pl"

_EXTERNAL_ID_RE = re.compile(r"mzn(\d+)")
_FLOOR_RE = re.compile(r"pi[eę]tro\s*(\d+)(?:/(\d+))?")
_PARTRER_RE = re.compile(r"parter(?:/(\d+))?", re.IGNORECASE)
_ROOMS_RE = re.compile(r"(\d+)\s*pok")
_AREA_RE = re.compile(r"([\d\s\xa0]+(?:,\d+)?)\s*m")
_PRICE_RE = re.compile(r"([\d\s\xa0]+)\s*zł")
_CITY_SLUGS = ("gdansk", "gdynia", "sopot", "rumia", "reda", "wejherowo")


def _money(text: str | None) -> Decimal | None:
    """Parse a Polish price string like '630 000 zł' into a Decimal."""
    if not text:
        return None
    cleaned = text.replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,]", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation, ValueError:
        return None


def _area(text: str | None) -> float | None:
    """Parse a Polish area string like '36 m²' into a float."""
    if not text:
        return None
    cleaned = text.replace("\xa0", "").replace(" ", "").replace("m²", "").replace("m2", "").strip()
    cleaned = re.sub(r"[^\d,]", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError, TypeError:
        return None


def _rooms(text: str | None) -> int | None:
    """Extract rooms count from text like '2 pokoje'."""
    if not text:
        return None
    match = _ROOMS_RE.search(text)
    return int(match.group(1)) if match else None


def _floor(text: str | None) -> int | None:
    """Extract floor number from text like 'piętro 4/4' or 'parter/3'."""
    if not text:
        return None
    match = _FLOOR_RE.search(text)
    if match:
        return int(match.group(1))
    match = _PARTRER_RE.search(text)
    if match:
        return 0
    return None


def _total_floors(text: str | None) -> int | None:
    """Extract total floors from text like 'piętro 4/4'."""
    if not text:
        return None
    match = _FLOOR_RE.search(text)
    if match and match.group(2):
        return int(match.group(2))
    match = _PARTRER_RE.search(text)
    if match and match.group(1):
        return int(match.group(1))
    return None


def _external_id(url: str) -> str:
    """Extract the external ID from a Morizon URL."""
    match = _EXTERNAL_ID_RE.search(url)
    if match:
        return f"mzn{match.group(1)}"
    return url.rstrip("/").split("/")[-1]


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
        if value and "nuxt-assets" not in value and ".svg" not in value:
            return value
    srcset = node.attrs.get("srcset", "")
    if srcset:
        url = srcset.split(",")[0].strip().split(" ")[0]
        if "nuxt-assets" not in url and ".svg" not in url:
            return url
    return ""


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip(" ,")
    return cleaned or None


_KNOWN_VOIVODESHIPS = {
    "pomorskie",
    "małopolskie",
    "mazowieckie",
    "dolnośląskie",
    "wielkopolskie",
    "śląskie",
    "łódzkie",
    "podkarpackie",
    "warmińsko-mazurskie",
    "zachodniopomorskie",
    "kujawsko-pomorskie",
    "świętokrzyskie",
    "lubelskie",
    "podlaskie",
    "opolskie",
    "lubuskie",
}


def _split_location(text: str | None) -> tuple[str | None, str | None, str | None]:
    """Split 'Street, District, City, voivodeship' into (city, district, street)."""
    cleaned = _clean_text(text)
    if not cleaned:
        return None, None, None
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if parts and parts[-1].lower() in _KNOWN_VOIVODESHIPS:
        parts = parts[:-1]
    city = district = street = None
    if len(parts) >= 3:
        street = parts[0]
        district = parts[1]
        city = parts[2]
    elif len(parts) == 2:
        first, city = parts
        if looks_like_street_or_code(first):
            street = first
        else:
            district = first
    elif len(parts) == 1:
        city = parts[0]
    if looks_like_street_or_code(district):
        street = street or district
        district = None
    return city, district, street


def _street_from_morizon_url(url: str) -> str | None:
    slug = url.rstrip("/").split("/")[-1]
    if "-mzn" in slug:
        slug = slug.rsplit("-mzn", 1)[0]
    parts = [part for part in slug.split("-") if part]
    for city in _CITY_SLUGS:
        if city in parts:
            idx = parts.index(city)
            tail = parts[idx + 1 :]
            while tail and re.fullmatch(r"\d+m2|\d+", tail[-1]):
                tail = tail[:-1]
            if tail:
                return " ".join(word.capitalize() for word in tail)
    return None


def _fix_street_from_url(
    url: str,
    district: str | None,
    street: str | None,
) -> tuple[str | None, str | None]:
    url_street = _street_from_morizon_url(url)
    if not url_street:
        return district, street
    if district and district.casefold() == url_street.casefold():
        return None, street or district
    return district, street or url_street


def _fix_gdansk_location(
    title: str | None,
    city: str | None,
    district: str | None,
) -> tuple[str | None, str | None]:
    if title and "gdańsk" in title.lower() and city and city.lower() != "gdańsk":
        return "Gdańsk", district or city
    return city, district


def _parse_search_card(card) -> RawListing | None:
    """Parse a single listing card from the search results page."""
    link = card.css_first("a.property-card")
    if not link:
        link = card.css_first("a[href*='/oferta/']")
    if not link:
        return None

    raw_href = link.attrs.get("href", "")
    url = _absolute_url(raw_href)
    if not url:
        return None
    external_id = _external_id(url)

    title_el = card.css_first(".property-card__title")
    title = title_el.text().strip() if title_el else ""

    price_el = card.css_first('[data-cy="propertyCardPrice"]')
    price = _money(price_el.text() if price_el else None)

    area_el = card.css_first('[data-cy="cardPropertyInfoArea"]')
    area_m2 = _area(area_el.text() if area_el else None)

    rooms_el = card.css_first('[data-cy="cardPropertyInfoRooms"]')
    rooms_val = _rooms(rooms_el.text() if rooms_el else None)

    floor_el = card.css_first('[data-cy="cardPropertyInfoFloor"]')
    floor_text = floor_el.text().strip() if floor_el else None
    floor_val = _floor(floor_text)
    total_floors_val = _total_floors(floor_text)

    location_el = card.css_first(".property-card__location span")
    loc_text = location_el.text() if location_el else None
    city_val, district_val, street_val = _split_location(loc_text)
    city_val, district_val = _fix_gdansk_location(title, city_val, district_val)
    district_val, street_val = _fix_street_from_url(url, district_val, street_val)

    images: list[str] = []
    for img in card.css(".property-card__image img, .card-gallery img"):
        src = _image_url(img)
        if src and src not in images:
            images.append(src)

    return RawListing(
        source_id="morizon",
        external_id=external_id,
        url=url,
        title=title,
        price=price,
        area_m2=area_m2,
        rooms=rooms_val,
        floor=floor_val,
        total_floors=total_floors_val,
        city=city_val,
        district=district_val,
        street=street_val,
        images=unique_listing_images(images),
    )


def _json_ld_detail(tree: HTMLParser) -> dict:
    """Extract listing details from JSON-LD structured data."""
    detail: dict = {}
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("@type") != "Offer":
            continue
        if data.get("description") and not detail.get("description"):
            detail["description"] = data["description"]
        item_offered = data.get("itemOffered", {})
        if isinstance(item_offered, dict):
            name = item_offered.get("name")
            if name and not detail.get("title"):
                detail["title"] = name
        offers = data.get("offers", data)
        if isinstance(offers, dict):
            price_val = offers.get("price")
            if price_val is not None and not detail.get("price"):
                try:
                    detail["price"] = Decimal(str(price_val))
                except InvalidOperation, ValueError:
                    pass
            currency = offers.get("priceCurrency", "PLN")
            if currency != "PLN":
                detail["currency"] = currency
        break
    return detail


class MorizonScraper:
    source_id = "morizon"
    display_name = "Morizon"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build a Morizon.pl search URL for the given criteria."""
        city = criteria.city.strip().lower().replace("ł", "l")
        city = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
        city = re.sub(r"\s+", "-", city.strip())
        url = f"{_BASE_URL}/mieszkania/{city}/"
        if page > 1:
            url += f"?page={page}"
        return url

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse a Morizon.pl search results page and return RawListings."""
        tree = HTMLParser(html)
        cards = tree.css(".card[data-cy='card']")
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in cards:
            listing = _parse_search_card(card)
            if listing is None:
                continue
            if listing.external_id in seen_ids:
                continue
            seen_ids.add(listing.external_id)
            listings.append(listing)

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse a Morizon.pl detail page; returns a RawListing."""
        external_id = _external_id(url)
        tree = HTMLParser(html)

        h1 = tree.css_first("h1")
        title = h1.text().strip() if h1 else ""

        price_el = tree.css_first('[data-cy="propertyCardPrice"], .property-card__price--main')
        price = _money(price_el.text() if price_el else None)

        description: str | None = None
        desc_el = tree.css_first(".description__content, .description")
        if desc_el:
            raw = desc_el.text(strip=True)
            description = raw if raw else None

        json_ld = _json_ld_detail(tree)
        if not description and json_ld.get("description"):
            description = json_ld["description"]
        if not title and json_ld.get("title"):
            title = json_ld["title"]
        if price is None and json_ld.get("price"):
            price = json_ld["price"]

        location_el = tree.css_first(".property-card__location span")
        loc_text = location_el.text() if location_el else None
        city_val, district_val, street_val = _split_location(loc_text)
        city_val, district_val = _fix_gdansk_location(title, city_val, district_val)
        district_val, street_val = _fix_street_from_url(url, district_val, street_val)

        area_el = tree.css_first('[data-cy="cardPropertyInfoArea"]')
        area_m2 = _area(area_el.text() if area_el else None)

        rooms_el = tree.css_first('[data-cy="cardPropertyInfoRooms"]')
        rooms_val = _rooms(rooms_el.text() if rooms_el else None)

        floor_el = tree.css_first('[data-cy="cardPropertyInfoFloor"]')
        floor_text = floor_el.text().strip() if floor_el else None
        floor_val = _floor(floor_text)
        total_floors_val = _total_floors(floor_text)

        images: list[str] = []
        for img in tree.css(".card-gallery img, .property-card__image img, .gallery img"):
            src = _image_url(img)
            if src and src not in images:
                images.append(src)

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=title,
            price=price,
            area_m2=area_m2,
            rooms=rooms_val,
            floor=floor_val,
            total_floors=total_floors_val,
            city=city_val,
            district=district_val,
            street=street_val,
            description=description,
            images=unique_listing_images(images),
        )


register(MorizonScraper())
