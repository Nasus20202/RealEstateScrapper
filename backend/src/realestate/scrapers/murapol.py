"""Murapol.pl scraper — nationwide developer, parses rendered DOM cards."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import fetch_json
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://murapol.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
}


def _absolute_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return _BASE_URL + href


def _slug(url: str) -> str:
    path = url.rstrip("/").split("/")[-1]
    return path or url


def _money(text: str | None) -> Decimal | None:
    if not text:
        return None
    match = re.search(
        r"(?<![-\w])(\d[\d\s\xa0]*(?:,\d+)?)\s*(?:zł|PLN)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    cleaned = match.group(1).replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,]", "", cleaned).replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation, ValueError:
        return None


def _area(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:m2|m²)", text, flags=re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,]", "", cleaned).replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except TypeError, ValueError:
        return None


def _rooms(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d+)\s*(?:pok|poko)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except TypeError, ValueError:
        return None


def _int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _city_from_text(text: str) -> str | None:
    for name in _CITY_MAP.values():
        if name.lower() in text.lower():
            return name
    return None


def _investment_from_url(url: str) -> str | None:
    return _slug(url) if url else None


def _image_url(node) -> str:
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        value = node.attributes.get(attr, "") or ""
        if value:
            return _absolute_url(value)
    srcset = node.attributes.get("srcset", "") or ""
    if srcset:
        return _absolute_url(srcset.split(",")[0].strip().split(" ")[0])
    return ""


class MurapolScraper:
    source_id = "murapol"
    display_name = "Murapol"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        city_slug = ""
        if criteria.city:
            normalized = unicodedata.normalize(
                "NFKD", criteria.city.strip().lower().replace("ł", "l")
            )
            city_slug = normalized.encode("ascii", "ignore").decode("ascii")
            city_slug = re.sub(r"\s+", "-", city_slug.strip())
        if city_slug == "gdansk":
            return f"{_BASE_URL}/oferta/gdansk/mieszkania"
        return f"{_BASE_URL}/oferta"

    def _parse_search_direct(self, html: str, city_slug: str) -> list[RawListing]:
        """Extract investment slugs directly from rendered HTML."""
        tree = HTMLParser(html)
        seen: dict[str, str] = {}

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "") or ""
            if not href:
                continue
            path = href.split("?")[0].rstrip("/")
            flat_match = re.search(r"/oferta/([^/]+)/(murapol-[^/]+)/[^/]+$", path)
            if not flat_match:
                continue
            lc = flat_match.group(1)
            inv = flat_match.group(2)
            if city_slug and lc != city_slug:
                continue
            seen[inv] = lc
        return [
            RawListing(
                source_id=self.source_id,
                external_id=inv,
                url=_absolute_url(f"/oferta/{lc}/{inv}"),
                title=inv,
                city=_CITY_MAP.get(lc),
                market="primary",
                attributes={"investment": inv},
            )
            for inv, lc in seen.items()
        ]

    def parse_search(self, html: str) -> list[RawListing]:
        city_slug = ""
        if self._last_city:
            normalized = unicodedata.normalize(
                "NFKD", self._last_city.strip().lower().replace("ł", "l")
            )
            city_slug = normalized.encode("ascii", "ignore").decode("ascii")
            city_slug = re.sub(r"\s+", "-", city_slug.strip())

        # Try direct extraction from rendered HTML first
        direct = self._parse_search_direct(html, city_slug)
        if direct:
            return direct

        # Detect investment page (redirected from search) via API ID attribute
        id_match = re.search(r'data-search-investment-id-value="(\d+)"', html)
        if id_match:
            inv_slug = None
            can_re = (
                r'<link\s+rel="canonical"\s+href="[^"]*'
                r'/oferta/[^/]+/([^/?"]+)'
            )
            can_match = re.search(can_re, html)
            if can_match:
                inv_slug = can_match.group(1)
            if not inv_slug:
                og_re = (
                    r'<meta\s+property="og:url"\s+content="[^"]*'
                    r'/oferta/[^/]+/([^/?"]+)'
                )
                og_match = re.search(og_re, html)
                if og_match:
                    inv_slug = og_match.group(1)
            if not inv_slug:
                inv_slug = f"murapol-investment-{id_match.group(1)}"

            city = _city_from_text(html) or _CITY_MAP.get(city_slug)
            url_part = f"/oferta/{city_slug}/{inv_slug}" if city_slug else f"/oferta/{inv_slug}"
            return [
                RawListing(
                    source_id=self.source_id,
                    external_id=inv_slug,
                    url=_absolute_url(url_part),
                    title=inv_slug,
                    city=city,
                    market="primary",
                    attributes={"investment": inv_slug},
                )
            ]

        return []

    def _parse_individual_apartments(
        self,
        html: str,
        url: str,
        ext_id: str,
    ) -> list[RawListing] | None:
        """Parse individual apartment cards from a Murapol investment detail page."""
        tree = HTMLParser(html)
        page_text = tree.body.text(strip=True) if tree.body else ""
        city = _city_from_text(page_text)
        apartments: list[RawListing] = []

        keywords = r"(?:mieszkanie|apartament|flat|cena|oferta|pokoj|metra|powierzchnia)"
        if not re.search(keywords, page_text[:5000], re.IGNORECASE):
            return None

        for card in tree.css(
            "[class*=flat], [class*=apartment], [class*=offer], "
            "[class*=mieszkanie], [class*=property-card], [class*=listing-card], "
            "[class*=investment-item], [data-id], [class*=card]"
        ):
            card_text = card.text(separator=" ", strip=True)
            if len(card_text) < 15:
                continue

            price = _money(card_text)
            area_m2 = _area(card_text)
            if price is None and area_m2 is None:
                continue

            flat_id = card.attributes.get("data-id") or card.attributes.get("data-flat-id")
            if not flat_id:
                id_match = re.search(r"(\d+)\s*(?:m²|m2|zł)", card_text[:50])
                flat_id = id_match.group(1) if id_match else str(abs(hash(card_text)) % 100000)

            title_el = card.css_first("h2, h3, h4, [class*=title], [class*=name]")
            title = title_el.text(strip=True) if title_el else f"Mieszkanie {flat_id}"

            rooms = _rooms(card_text)

            floor_val = None
            floor_m = re.search(r"pi[eę]tro\s*(\d+)", card_text)
            if floor_m:
                floor_val = _int(floor_m.group(1))

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            apartments.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{flat_id}",
                    url=url,
                    title=title,
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={"investment": ext_id, "flat_id": flat_id},
                )
            )

        return apartments if apartments else None

    def _parse_apartments_api(self, html: str, ext_id: str) -> list[RawListing] | None:
        id_match = re.search(r'data-search-investment-id-value="(\d+)"', html)
        if not id_match:
            return None
        inv_id = id_match.group(1)
        try:
            data = fetch_json(
                f"{_BASE_URL}/api/investment/apartments/{inv_id}?page=1&locale=pl&type=tiles&status=2"
            )
        except Exception:
            return None
        items = data.get("apartments", []) if isinstance(data, dict) else []
        if not items:
            return None

        city = items[0].get("cityName")
        if city:
            city_map_vals = {v.lower() for v in _CITY_MAP.values()}
            if city.lower() not in city_map_vals:
                city = _city_from_text(html) or _city_from_text(html)
        inv_name = items[0].get("investmentName", ext_id)

        listings: list[RawListing] = []
        for apt in items:
            flat_id = str(apt.get("apartmentId", ""))
            sku = apt.get("sku", "")
            price_m2_str = (apt.get("currentPriceM2") or "0").replace(" ", "").replace(",", ".")
            area_str = (apt.get("area") or "0").replace(",", ".")
            price_m2 = Decimal(price_m2_str) if price_m2_str and price_m2_str != "0" else None
            area_m2 = float(area_str) if area_str and area_str != "0" else None
            price = price_m2 * Decimal(str(area_m2)) if price_m2 and area_m2 else None

            floor_match = re.search(r"(\d+)", apt.get("floor", ""))
            floor_val = int(floor_match.group(1)) if floor_match else None
            rooms_val = apt.get("rooms")

            images: list[str] = []
            cover = apt.get("coverPhotoUrl")
            if cover:
                images.append(_absolute_url(cover))

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{flat_id}",
                    url=_absolute_url(apt.get("apartmentUrl", "")),
                    title=f"{inv_name} {sku}",
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms_val,
                    floor=floor_val,
                    city=city or _city_from_text(html),
                    street=apt.get("street"),
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": inv_name,
                        "flat_id": flat_id,
                        "sku": sku,
                        "status": "available" if apt.get("status") == 2 else "unknown",
                    },
                )
            )
        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)

        apartments = self._parse_apartments_api(html, ext_id)
        if apartments:
            return apartments

        apartments = self._parse_individual_apartments(html, url, ext_id)
        if apartments:
            return apartments

        tree = HTMLParser(html)

        h1 = tree.css_first("h1")
        title = h1.text(strip=True) if h1 else ""
        if not title:
            t = tree.css_first("title")
            title = t.text(strip=True) if t else ext_id

        desc_el = tree.css_first(
            ".description, .content, article, [class*=description], [class*=Description]"
        )
        description: str | None = None
        if desc_el:
            raw = desc_el.text(strip=True)
            description = raw if raw else None

        images: list[str] = []
        for img in tree.css("img[src]"):
            src = _image_url(img)
            if src and src not in images and not src.endswith(".svg"):
                images.append(src)

        city = _city_from_text(title) or _city_from_text(url)

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


register(MurapolScraper())
