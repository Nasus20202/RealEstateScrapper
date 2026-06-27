"""Robyg.pl scraper — developer active in Tricity, Warsaw, Wrocław, Poznań, Łódź."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.districts import district_from_investment
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.robyg.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "warszawa": "Warszawa",
    "wroclaw": "Wrocław",
    "poznan": "Poznań",
    "lodz": "Łódź",
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


class RobygScraper:
    source_id = "robyg"
    display_name = "Robyg"

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
        if city_slug in ("gdansk", "gdynia"):
            return f"{_BASE_URL}/{city_slug}"
        return f"{_BASE_URL}"

    def _parse_search_direct(self, html: str, city_slug: str) -> list[RawListing]:
        """Extract investment links from the city page HTML."""
        if not city_slug:
            return []

        pattern = re.escape(city_slug) + r"/inwestycje/([^/\"'?\s]+)"
        listings: list[RawListing] = []
        seen: set[str] = set()

        for link in re.finditer(pattern, html):
            slug = link.group(1)
            if slug in seen or slug == "zrealizowane":
                continue
            seen.add(slug)
            url = _absolute_url(f"/{city_slug}/inwestycje/{slug}")
            city = _city_from_text(html)
            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=slug,
                    url=url,
                    title=slug,
                    city=city or _CITY_MAP.get(city_slug, city_slug),
                    district=district_from_investment(slug),
                    market="primary",
                    attributes={"investment": slug},
                )
            )
        return listings

    def parse_search(self, html: str) -> list[RawListing]:
        city_slug = ""
        if self._last_city:
            normalized = unicodedata.normalize(
                "NFKD", self._last_city.strip().lower().replace("ł", "l")
            )
            city_slug = normalized.encode("ascii", "ignore").decode("ascii")
            city_slug = re.sub(r"\s+", "-", city_slug.strip())

        # Try direct regex extraction first
        direct = self._parse_search_direct(html, city_slug)
        if direct:
            return direct

        # Fallback: broad DOM selectors
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in tree.css(
            "[class*=card], [class*=Card], [class*=invest], [class*=Invest], "
            "[class*=project], [class*=Project], [class*=offer], [class*=Offer], "
            "[class*=tile], [class*=Tile], [class*=listing], [class*=Listing]"
        ):
            link = card.css_first("a[href]")
            href = link.attributes.get("href", "") if link else ""
            name_el = card.css_first(
                "h1, h2, h3, h4, [class*=name], [class*=Name], [class*=title], [class*=Title]"
            )
            text = name_el.text(strip=True) if name_el else ""

            if not text:
                continue

            url = _absolute_url(href.split("#")[0]) if href else ""
            ext_id = _investment_from_url(url) or re.sub(r"[^a-z0-9]+", "-", text.lower()).strip(
                "-"
            )

            if not ext_id or ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            card_text = card.text(separator=" ", strip=True)
            city = _city_from_text(card_text)

            if self._last_city:
                requested = _city_from_text(self._last_city) or self._last_city
                if city and requested.lower() not in city.lower():
                    continue

            price_val = _money(card_text)
            area_val = _area(card_text)
            rooms_val = _rooms(card_text)

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=url or f"{_BASE_URL}/",
                    title=text,
                    price=price_val,
                    area_m2=area_val,
                    rooms=rooms_val,
                    city=city,
                    district=district_from_investment(ext_id) or district_from_investment(text),
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={"investment": ext_id},
                )
            )

        return listings

    def _parse_individual_apartments(
        self,
        html: str,
        url: str,
        ext_id: str,
    ) -> list[RawListing] | None:
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
            "[class*=card], [data-id], [class*=investment-item]"
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
                    district=district_from_investment(ext_id),
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={"investment": ext_id, "flat_id": flat_id},
                )
            )

        return apartments if apartments else None

    def _parse_apartments_api(self, html: str, ext_id: str) -> list[RawListing] | None:
        """Parse individual flats from the SSR-rendered page HTML."""
        tree = HTMLParser(html)
        items = tree.css(".item[data-id]")
        if not items:
            return None

        city = _city_from_text(html)

        listings: list[RawListing] = []
        for item in items:
            flat_id = item.attributes.get("data-id")
            if not flat_id:
                continue

            status_code = item.attributes.get("data-status", "")
            detail_url = item.attributes.get("data-url", "")

            name_el = item.css_first(".td-number a")
            unit_name = name_el.text(strip=True) if name_el else ""

            item_text = item.text(separator=" ", strip=True)

            floor_val = None
            floor_m = re.search(r"Piętro:\s*(\d+)", item_text)
            if floor_m:
                floor_val = _int(floor_m.group(1))

            rooms = None
            rooms_m = re.search(r"Pokoje:\s*(\d+)", item_text)
            if rooms_m:
                rooms = _int(rooms_m.group(1))

            area_m2 = None
            area_el = item.css_first(".area-usable")
            if area_el:
                area_text = area_el.text(strip=True)
                # Remove m²/m2 suffix before cleaning
                area_text = re.sub(r"\s*m\s*2?\s*$", "", area_text, flags=re.IGNORECASE)
                cleaned = area_text.replace(",", ".").replace("\xa0", "").replace(" ", "")
                if cleaned:
                    area_m2 = _float(cleaned)

            price = None
            price_el = item.css_first(".price-pln:not(.price-pln-m2)")
            if price_el:
                price_text = price_el.text(strip=True)
            else:
                price_text = ""
            if not price_text:
                price_m = re.search(
                    r"(\d[\d\s\xa0]*(?:,\d+)?)\s*zł(?!/m)",
                    item_text,
                )
                if price_m:
                    price_text = price_m.group(0)
            if price_text:
                price = _money(price_text)
                if price is not None and price < 1000:
                    price = None

            images: list[str] = []
            img_el = item.css_first("img")
            if img_el:
                src = _image_url(img_el)
                if src and not src.endswith(".svg"):
                    images = [src]

            title = f"{ext_id} {unit_name}" if unit_name else f"{ext_id} {flat_id}"
            status = "available" if status_code in ("3", "4") else "unknown"

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{flat_id}",
                    url=_absolute_url(detail_url) if detail_url else "",
                    title=title,
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    district=district_from_investment(ext_id),
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": ext_id,
                        "flat_id": flat_id,
                        "status": status,
                    },
                )
            )

        return listings if listings else None

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)

        # Try API-based extraction first
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
            district=district_from_investment(ext_id) or district_from_investment(title),
            market="primary",
        )


register(RobygScraper())
