"""Hossa.gda.pl scraper — Tricity property developer, parses rendered DOM cards."""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.hossa.gda.pl"
_APARTMENTS_LIMIT = 500

# City slug → Polish city name
_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
}

# Maps ASCII-folded city slug → hossa URL path
_CITY_URL_PATH: dict[str, str] = {
    "gdansk": "mieszkania",
    "gdynia": "mieszkania",
    "sopot": "mieszkania",
}


def _city_path(city: str) -> str:
    """Return the hossa URL path for the given city (ASCII-folded match)."""
    normalized = unicodedata.normalize("NFKD", city.strip().lower().replace("ł", "l"))
    slug = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"\s+", "-", slug.strip())
    return _CITY_URL_PATH.get(slug, "mieszkania")

# Navigation/utility paths to exclude (these are never real estate offers)
_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/aktualnosci/",
        "/kredyty/",
        "/podklucz/",
        "/blog/",
        "/firma/",
        "/kariera/",
        "/kontakt/",
        "/oferty-specjalne/",
        "/kontakt/biura-sprzedazy/",
        "/polityka-prywatnosci/",
        "/strategie/",
        "/lokale-uzytkowe/",
        "/wyniki-wyszukiwania",
    }
)

# Domains that are never offer pages
_EXCLUDED_DOMAINS: tuple[str, ...] = (
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "linkedin.com",
    "akcjonariusze",
)


def _absolute_url(href: str) -> str:
    """Return an absolute hossa.gda.pl URL from a possibly relative href."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return _BASE_URL + href


def _slug(url: str) -> str:
    """Extract the last path segment (slug) from a URL."""
    path = url.rstrip("/").split("/")[-1]
    return path or url


def _money(text: str | None) -> Decimal | None:
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", text.strip()):
        try:
            return Decimal(text.strip())
        except (InvalidOperation, ValueError):
            return None
    match = re.search(r"(?<![-\w])(\d[\d\s\xa0]*(?:,\d+)?)\s*zł", text, flags=re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,]", "", cleaned).replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _area(text: str | None) -> float | None:
    if not text:
        return None
    if re.fullmatch(r"\d+(?:[,.]\d+)?", text.strip()):
        try:
            return float(text.strip().replace(",", "."))
        except (TypeError, ValueError):
            return None
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*m", text, flags=re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,]", "", cleaned).replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _rooms(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d+)\s*(?:pok|poko)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _image_url(node) -> str:
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        value = node.attributes.get(attr, "") or ""
        if value:
            return _absolute_url(value)
    style = node.attributes.get("style", "") or ""
    match = re.search(r"url\(['\"]?([^)'\"]+)", style)
    if match:
        return _absolute_url(match.group(1))
    srcset = node.attributes.get("srcset", "") or ""
    if srcset:
        return _absolute_url(srcset.split(",")[0].strip().split(" ")[0])
    return ""


def _city_from_slug(slug: str) -> str | None:
    """Derive city name from a URL slug like 'nowe-mieszkania-gdansk'."""
    for key, name in _CITY_MAP.items():
        if key in slug:
            return name
    return None


def _city_from_text(text: str) -> str | None:
    for name in _CITY_MAP.values():
        if name.lower() in text.lower():
            return name
    return None


def _district_from_place(place: str | None, city: str | None) -> str | None:
    if not place or not city:
        return None
    return place.replace(city, "", 1).strip() or None


def _is_offer_link(href: str, text: str) -> bool:
    """Return True if this link leads to an offer/investment category page."""
    if not href or not text:
        return False
    if href.startswith("tel:") or href.startswith("mailto:"):
        return False
    if any(domain in href for domain in _EXCLUDED_DOMAINS):
        return False
    # Must be on the hossa domain or a relative path
    if "hossa.gda.pl" not in href and not href.startswith("/"):
        return False
    # Strip fragment
    clean = href.split("#")[0].rstrip("/") + "/"
    # Derive the path component
    path = clean.replace("https://www.hossa.gda.pl", "").replace(
        "https://hossa.gda.pl", ""
    )
    if path in _EXCLUDED_PATHS:
        return False
    # Accept paths that contain offer-related keywords
    offer_keywords = ("mieszkani", "apartament", "loft", "inwestycj", "osiedl")
    return any(kw in path.lower() for kw in offer_keywords)


class HossaScraper:
    source_id = "hossa"
    display_name = "Hossa"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        """Return the Hossa city-specific offers page URL for the given criteria."""
        self._last_city = criteria.city
        path = _city_path(criteria.city)
        return f"{_BASE_URL}/{path}/"

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse rendered Hossa flat cards; never return city/category links."""
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in tree.css(".o-card__inner"):
            outer_card = card.parent if card.parent is not None else card
            link = card.css_first("a.btn[href], a[href]")
            href = link.attributes.get("href", "") if link else ""
            name_el = card.css_first(".o-card__name, h1, h2, h3")
            text = name_el.text(strip=True) if name_el else ""

            if not href or not text:
                continue

            url = _absolute_url(href.split("#")[0])
            if not url:
                continue

            ext_id = (
                card.attributes.get("data-flat-id")
                or card.attributes.get("data-offer-id")
                or _slug(url)
            )
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            card_text = card.text(separator=" ", strip=True)
            place_el = card.css_first(".o-card__place")
            place = place_el.text(strip=True) if place_el else None
            address_el = card.css_first(".o-card__address")
            street = None
            if address_el:
                street_parts = [span.text(strip=True) for span in address_el.css("span")]
                street = ", ".join(part for part in street_parts if part) or None
            city = _city_from_text(place or card_text) or _city_from_slug(ext_id)
            if self._last_city and city:
                requested = _city_from_text(self._last_city) or self._last_city
                if requested.lower() not in city.lower():
                    continue
            district = _district_from_place(place, city)
            api_url = (
                f"{_BASE_URL}/api/apartments/?inv={ext_id}&type=a&"
                f"a_status=dost%C4%99pny&limit={_APARTMENTS_LIMIT}&page=1"
            )
            images: list[str] = []
            outer_image = _image_url(outer_card)
            if outer_image and not outer_image.endswith(".svg"):
                images.append(outer_image)
            for img in outer_card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=api_url,
                    title=text,
                    price=_money(card_text),
                    area_m2=_area(card_text),
                    rooms=_rooms(card_text),
                    city=city,
                    district=district,
                    street=street,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={"investment": ext_id, "investment_url": url},
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        if "/api/apartments/" in url:
            return self._parse_apartments_api(html, url)

        """Parse a Hossa investment/offer detail page; returns a minimal RawListing."""
        ext_id = _slug(url)
        tree = HTMLParser(html)

        # Title: try h1, fall back to page <title>
        h1 = tree.css_first("h1")
        title = h1.text(strip=True) if h1 else ""
        if not title:
            t = tree.css_first("title")
            title = t.text(strip=True) if t else ext_id

        # Description
        desc_el = tree.css_first(
            ".description, .content, article, .investment-description"
        )
        description: str | None = None
        if desc_el:
            raw = desc_el.text(strip=True)
            description = raw if raw else None

        # Images
        images: list[str] = []
        for img in tree.css("img[src]"):
            src = _image_url(img)
            if src and src not in images and not src.endswith(".svg"):
                images.append(_absolute_url(src))

        city = _city_from_slug(_slug(url))

        return RawListing(
            source_id=self.source_id,
            external_id=ext_id,
            url=url,
            title=title,
            description=description,
            images=images,
            city=city,
            market="primary",
        )

    def _parse_apartments_api(self, body: str, url: str) -> list[RawListing]:
        raw_body = body.strip()
        if not raw_body.startswith("{"):
            tree = HTMLParser(body)
            raw_body = tree.body.text(strip=True) if tree.body else raw_body
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return []
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []

        query = parse_qs(urlparse(url).query)
        investment_slug = (query.get("inv") or [""])[0]
        listings: list[RawListing] = []
        for item in rows:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            item_id = item["id"]
            investment = str(item.get("investment_slug") or investment_slug)
            number = str(item.get("number") or item_id)
            images = []
            for media in item.get("media") or []:
                if isinstance(media, dict):
                    picture = media.get("picture") or media.get("thumb")
                    if isinstance(picture, str):
                        images.append(_absolute_url(picture))
            attributes = {
                "investment": investment,
                "building": item.get("building"),
                "availability": item.get("availability"),
                "status": item.get("status_label"),
                "price_per_usable_m2": item.get("price_per_usable_m2"),
                "tags": item.get("tags") or [],
            }
            attributes = {k: v for k, v in attributes.items() if v not in (None, "", [])}
            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"apartment-{item_id}",
                    url=f"{_BASE_URL}/{investment}/wyniki-wyszukiwania/#id={item_id}",
                    title=f"{investment.replace('-', ' ').title()} {number}",
                    price=_money(str(item.get("price") or "")),
                    area_m2=_area(str(item.get("area_usable") or item.get("area") or "")),
                    rooms=int(item["rooms"]) if item.get("rooms") is not None else None,
                    floor=int(item["floor"]) if item.get("floor") is not None else None,
                    description=item.get("description"),
                    attributes=attributes,
                    market="primary",
                    images=unique_listing_images(images),
                    raw=item,
                )
            )
        return listings


register(HossaScraper())
