"""Trojmiasto.pl classifieds scraper — parses listing data from DOM via selectolax.

Targets the "Nieruchomości: Sprzedam" sections (real estate for sale) on
https://ogloszenia.trojmiasto.pl/ — by default the secondary-market category
``nieruchomosci-sprzedam-rynek-wtorny`` (Tricity area), with the primary-market
category ``nieruchomosci-sprzedam-rynek-pierwotny`` selected when
``SearchCriteria.market == "primary"``. Pages are server-rendered, so the same
selectors work for plain-HTTP snapshots and browser-rendered HTML alike.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import (
    absolute_url,
    clean_text,
    image_url,
    looks_like_street_or_code,
    parse_area,
    parse_int_text,
    parse_money,
    parse_rooms,
)
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://ogloszenia.trojmiasto.pl"
_CATEGORY_SECONDARY = "nieruchomosci-sprzedam-rynek-wtorny"
_CATEGORY_PRIMARY = "nieruchomosci-sprzedam-rynek-pierwotny"

# Tricity-area cities that can appear at the start (or end, after a comma) of a
# card's location subtitle. Longest names first so "Pruszcz Gdański" wins over
# "Gdańsk" when the whole phrase is present.
_KNOWN_CITIES = (
    "Pruszcz Gdański",
    "Władysławowo",
    "Wejherowo",
    "Chwaszczyno",
    "Koleczkowo",
    "Gdańsk",
    "Gdynia",
    "Sopot",
    "Rumia",
    "Reda",
    "Puck",
    "Żukowo",
    "Kartuzy",
    "Tczew",
)

_FEATURE_SELECTOR = "li.details--icons--element--{key} .list__item__details__icons__element__desc"


def _external_id(url: str) -> str:
    """Extract the numeric offer ID from a trojmiasto.pl URL like ``...-ogl123.html``."""
    match = re.search(r"-ogl(\d+)\.html", url)
    return match.group(1) if match else url


def _feature_text(card, key: str) -> str | None:
    node = card.css_first(_FEATURE_SELECTOR.format(key=key))
    return clean_text(node.text()) if node else None


def _detail_field(tree: HTMLParser, field: str) -> str | None:
    node = tree.css_first(f".xogField--{field} .xogField__value")
    return clean_text(node.text()) if node else None


def _parse_floor_text(text: str | None) -> int | None:
    if not text:
        return None
    lowered = text.lower()
    if "parter" in lowered:
        return 0
    match = re.search(r"(\d+)\s*pi[eę]tro", lowered) or re.search(r"pi[eę]tro\s*(\d+)", lowered)
    if match:
        return int(match.group(1))
    return parse_int_text(text)


def _parse_page_time(tree: HTMLParser) -> datetime | None:
    return _parse_time_node(tree.css_first("time[datetime]"))


def _market_from_canonical(tree: HTMLParser) -> str:
    """Derive the listing market from the page's canonical category URL."""
    link = tree.css_first('link[rel="canonical"]')
    if link is not None:
        href = link.attrs.get("href", "")
        if _CATEGORY_PRIMARY in href:
            return "primary"
    return "secondary"


def _product_json_ld(tree: HTMLParser) -> dict | None:
    """Return the JSON-LD ``Product`` block describing the offer, if present."""
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
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def _split_location(text: str | None) -> tuple[str | None, str | None, str | None]:
    """Decompose a Trojmiasto.pl location subtitle into city/district/street.

    Handles observed formats: ``"Gdańsk Zaspa Rozstaje"``,
    ``"Gdańsk Śródmieście, Lawendowa"``, ``"Puck, Kolejowa"``,
    ``"Gdynia Chwarzno - Wiczlino, Stanisława Filipkowskiego"``, and postal-code
    form ``"80-180, Gdańsk"``. Unknown cities degrade to ``city=None``.
    """
    cleaned = clean_text(text)
    if not cleaned:
        return None, None, None

    for city in _KNOWN_CITIES:
        if cleaned.lower().startswith(city.lower()):
            remainder = cleaned[len(city) :].strip()
            had_comma = remainder.startswith(",")
            remainder = remainder.strip(" ,")
            if not remainder:
                return city, None, None
            if "," in remainder:
                before, after = remainder.split(",", 1)
                district = before.strip() or None
                street = after.strip() or None
                if district and looks_like_street_or_code(district):
                    street = ", ".join(part for part in (district, street) if part)
                    district = None
                return city, district, street
            if had_comma:
                # City followed by a comma and a single part: the part is a
                # street (e.g. "Puck, Kolejowa"), not a district.
                return city, None, remainder
            return city, remainder, None

    # City at the end, after a comma: "80-180, Gdańsk" or "Śródmieście, Gdańsk".
    match = re.search(r",\s*([^,]+)$", cleaned)
    if match and match.group(1).strip().lower() in {c.lower() for c in _KNOWN_CITIES}:
        city = match.group(1).strip()
        rest = cleaned[: match.start()].strip()
        if looks_like_street_or_code(rest):
            return city, None, rest
        return city, rest or None, None

    # No recognizable city: keep the whole text as a best-effort district.
    if looks_like_street_or_code(cleaned):
        return None, None, cleaned
    return None, cleaned, None


class TrojmiastoScraper:
    source_id = "trojmiasto"
    display_name = "Trojmiasto.pl"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Build a trojmiasto.pl sale category URL for the given criteria."""
        category = _CATEGORY_PRIMARY if criteria.market == "primary" else _CATEGORY_SECONDARY
        url = f"{_BASE_URL}/{category}/"
        if page > 1:
            url += f"?strona={page}"
        return url

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse a trojmiasto.pl search results page and return RawListings."""
        tree = HTMLParser(html)
        market = _market_from_canonical(tree)
        listings: list[RawListing] = []

        for card in tree.css("article.list__item[data-id]"):
            title_link = card.css_first(".list__item__content__title__name")
            if title_link is None:
                continue
            raw_href = title_link.attrs.get("href", "")
            url = absolute_url(raw_href, _BASE_URL)
            title = clean_text(title_link.text())
            if not title or not url:
                continue

            external_id = card.attrs.get("data-id") or _external_id(url)

            price = parse_money(_feature_text(card, "cena")) or parse_money(_price_node_text(card))
            area = parse_area(_feature_text(card, "powierzchnia"))
            rooms = parse_rooms(_feature_text(card, "l_pokoi"))
            floor = _parse_floor_text(_feature_text(card, "pietro"))
            year = parse_int_text(_feature_text(card, "rok_budowy"))

            location = card.css_first(".list__item__content__subtitle")
            city, district, street = _split_location(
                location.text() if location is not None else None
            )

            images: list[str] = []
            for img in card.css(".list__item__picture img"):
                src = image_url(img)
                if src:
                    images.append(src)

            time_node = card.css_first(".listItemFooter__date time")
            posted_at = _parse_time_node(time_node)

            attributes: dict = {}
            if year is not None:
                attributes["construction_year"] = year

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=str(external_id),
                    url=url,
                    title=title,
                    price=price,
                    area_m2=area,
                    rooms=rooms,
                    floor=floor,
                    city=city,
                    district=district,
                    street=street,
                    market=market,
                    attributes=attributes,
                    images=unique_listing_images(images),
                    posted_at=posted_at,
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse a trojmiasto.pl offer detail page; returns a RawListing."""
        external_id = _external_id(url)
        tree = HTMLParser(html)

        h1 = tree.css_first("h1.xogIndex__title")
        title = clean_text(h1.text()) if h1 is not None else None
        title = title or ""

        price = parse_money(_detail_field(tree, "cena"))
        area = parse_area(_detail_field(tree, "powierzchnia"))
        rooms = parse_rooms(_detail_field(tree, "l_pokoi")) or parse_int_text(
            _detail_field(tree, "l_pokoi")
        )
        floor = _parse_floor_text(_detail_field(tree, "pietro"))
        year = parse_int_text(_detail_field(tree, "rok_budowy"))

        city, district, street = _split_location(_detail_field(tree, "address"))

        product = _product_json_ld(tree)
        description: str | None = None
        if product:
            raw_desc = product.get("description")
            if isinstance(raw_desc, str) and raw_desc.strip():
                description = raw_desc
        if not description:
            meta = tree.css_first('meta[name="description"]')
            description = clean_text(meta.attrs.get("content")) if meta is not None else None

        images: list[str] = []
        if product and isinstance(product.get("image"), list):
            for value in product["image"]:
                if isinstance(value, str):
                    images.append(value)
        else:
            for img in tree.css(".xogPhotos img, .lazy"):
                src = image_url(img)
                if src:
                    images.append(src)

        attributes: dict = {}
        if year is not None:
            attributes["construction_year"] = year

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=title,
            price=price,
            area_m2=area,
            rooms=rooms,
            floor=floor,
            city=city,
            district=district,
            street=street,
            description=description,
            attributes=attributes,
            images=unique_listing_images(images),
            posted_at=_parse_page_time(tree),
        )


def _price_node_text(card) -> str | None:
    for selector in (
        ".list__item__price__value span",
        ".list__item__picture__price__currency",
    ):
        node = card.css_first(selector)
        if node is not None:
            value = clean_text(node.text())
            if value:
                return value
    return None


def _parse_time_node(node) -> datetime | None:
    if node is None:
        return None
    raw = node.attrs.get("datetime", "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace(" ", "T"))
    except ValueError:
        return None


register(TrojmiastoScraper())
