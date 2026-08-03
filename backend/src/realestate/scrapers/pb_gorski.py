"""PB Górski scraper — Tricity developer (Gdańsk, Gdynia, Chojnice)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://pbgorski.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "chojnice": "Chojnice",
}

_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/firma/",
        "/kontakt/",
        "/oferta/",
        "/gdansk/",
        "/gdynia/",
        "/kredyty/",
        "/lokale/",
        "/dzial-aranzacji/",
        "/aktualnosci/",
        "/kariera/",
        "/inwestycje-zrealizowane/",
        "/rewitalizacja-zabytkow/",
        "/polityka-prywatnosci/",
        "/rodo/",
        "/strategia-podatkowa/",
        "/mieszkania-gotowe-do-odbioru/",
        "/dla-inwestorow/",
    }
)


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
    match = re.search(r"(\d[\d\s]*(?:,\d+)?)\s*(?:zł|zł/m|PLN)", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"od\s+(\d[\d\s]*(?:,\d+)?)\s*(?:zł|PLN)", text, flags=re.IGNORECASE)
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


def _price_per_m2(text: str | None) -> Decimal | None:
    if not text:
        return None
    match = re.search(r"(\d[\d\s]*(?:,\d+)?)\s*zł/m", text, flags=re.IGNORECASE)
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
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*m", text, flags=re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace(",", ".")
    try:
        return float(cleaned)
    except TypeError, ValueError:
        return None


def _rooms(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d+)\s*(?:pok|poko)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:pok|poko)\w*\s*[:]?\s*(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


_FLAT_STATUS_MAP = {
    "wolne": "available",
    "dostepne": "available",
    "dostępne": "available",
    "zarezerwowane": "reserved",
    "sprzedane": "sold",
}


def _flat_status(text: str) -> str:
    lowered = text.lower()
    for key, status in _FLAT_STATUS_MAP.items():
        if key in lowered:
            return status
    return ""


def _int(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text.strip())
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except TypeError, ValueError:
        return None


def _image_url(node) -> str:
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        value = node.attributes.get(attr, "") if hasattr(node, "attributes") else ""
        if value:
            return _absolute_url(value)
    srcset = node.attributes.get("srcset", "") if hasattr(node, "attributes") else ""
    if srcset:
        return _absolute_url(srcset.split(",")[0].strip().split(" ")[0])
    return ""


def _area_range(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    match = re.search(r"(?:od|min\.?)\s*(\d+(?:[,.]\d+)?)\s*(?:m|do)", text, flags=re.IGNORECASE)
    match2 = re.search(r"(?:do|max\.?)\s*(\d+(?:[,.]\d+)?)\s*m", text, flags=re.IGNORECASE)
    min_area = None
    max_area = None
    if match:
        try:
            min_area = float(match.group(1).replace(",", "."))
        except TypeError, ValueError:
            pass
    if match2:
        try:
            max_area = float(match2.group(1).replace(",", "."))
        except TypeError, ValueError:
            pass
    return min_area, max_area


def _city_from_text(text: str) -> str | None:
    for name in _CITY_MAP.values():
        if name.lower() in text.lower():
            return name
    return None


def _city_from_url(url: str) -> str | None:
    url_lower = url.lower()
    for key, name in _CITY_MAP.items():
        if f"/{key}" in url_lower:
            return name
    return None


def _is_investment_link(href: str) -> bool:
    if not href:
        return False
    if href.startswith("tel:") or href.startswith("mailto:"):
        return False
    path = href.replace(_BASE_URL, "").rstrip("/")
    if path in _EXCLUDED_PATHS:
        return False
    if "/inwestycja/" in path:
        return True
    return False


class PBGorskiScraper:
    source_id = "pb-gorski"
    display_name = "PB Górski"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return f"{_BASE_URL}/oferta/"

    def parse_search(self, html: str) -> list[RawListing]:
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            if not _is_investment_link(href):
                continue

            url = _absolute_url(href.split("#")[0].split("?")[0])
            if not url:
                continue

            ext_id = _slug(url)
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            text = link.text(strip=True)
            if not text:
                text_el = link.css_first("h2, h3, h4, span, p")
                text = text_el.text(strip=True) if text_el else ext_id

            city = _city_from_url(url) or _city_from_text(text)
            if self._last_city and city:
                requested = _city_from_text(self._last_city) or self._last_city
                if requested.lower() not in city.lower():
                    continue

            card = link.parent if link.parent is not None else link
            card_text = card.text(separator=" ", strip=True) if card else text

            min_area, max_area = _area_range(card_text)
            area_m2 = max_area or min_area

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=url,
                    title=text,
                    price=_money(card_text),
                    area_m2=area_m2,
                    city=city,
                    market="primary",
                    attributes={
                        "investment": ext_id,
                        "investment_url": url,
                        "price_per_m2": str(_price_per_m2(card_text))
                        if _price_per_m2(card_text)
                        else None,
                    },
                )
            )

        return listings

    def _parse_individual_apartments(
        self,
        html: str,
        url: str,
        ext_id: str,
    ) -> list[RawListing] | None:
        """Parse individual apartment cards from a PB Górski investment detail page."""
        tree = HTMLParser(html)
        page_text = tree.body.text(strip=True) if tree.body else ""
        city = _city_from_url(url) or _city_from_text(page_text)

        cards = tree.css(".apartment-box")

        # Investment pages that only advertise per-m² pricing (or are plain
        # descriptions) carry no apartment cards — skip them.
        if not cards:
            if re.search(r"zł/m[²2]|cena.*od.*zł/m", page_text[:5000], re.IGNORECASE):
                return None
            keywords = r"(?:mieszkanie|apartament|flat|oferta|pokoje|metra)"
            if not re.search(keywords, page_text[:5000], re.IGNORECASE):
                return None
            return None

        apartments: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in cards:
            card_text = card.text(separator=" ", strip=True)
            if len(card_text) < 10:
                continue

            price_el = card.css_first("[class*=price]")
            price = _money(price_el.text(strip=True)) if price_el else _money(card_text)
            area_m2 = _area(card_text)
            if price is None and area_m2 is None:
                continue

            title_el = card.css_first("h2, h3, h4, [class~='h4'], [class*=title], [class*=name]")
            title = title_el.text(strip=True) if title_el else ""
            if not title:
                title_match = re.search(r"Mieszkanie\s+\S+", card_text, re.IGNORECASE)
                title = title_match.group(0) if title_match else ""

            flat_id = card.attributes.get("data-id") or card.attributes.get("data-flat-id")
            if not flat_id:
                link = card.css_first("a[href*='mieszkanie-']")
                if link:
                    flat_id = _slug(link.attributes.get("href", ""))
            if not flat_id:
                id_match = re.search(r"Mieszkanie\s+([A-Za-z]?\d+)", title, re.IGNORECASE)
                flat_id = f"mieszkanie-{id_match.group(1).lower()}" if id_match else None
            if not flat_id:
                continue

            ext_id_full = f"{ext_id}-{flat_id}"
            if ext_id_full in seen_ids:
                continue
            seen_ids.add(ext_id_full)

            rows = card.css(".apartment-box-list > div")
            if not rows:
                rows = [card]

            rooms = None
            floor_val = None
            status = ""
            for row in rows:
                row_text = row.text(separator=" ", strip=True)
                rooms_val = _rooms(row_text)
                if rooms_val is not None:
                    rooms = rooms_val
                floor_m = re.search(r"pi[eę]tro\s*[:]?\s*(\d+)", row_text, re.IGNORECASE)
                if floor_m:
                    floor_val = _int(floor_m.group(1))
                elif re.search(r"pi[eę]tro\s*[:]?\s*parter", row_text, re.IGNORECASE):
                    floor_val = 0
                if not status:
                    status = _flat_status(row_text)
            if not status:
                status = _flat_status(card_text)

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            apartments.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id_full,
                    url=url,
                    title=title or f"Mieszkanie {flat_id}",
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": ext_id,
                        "flat_id": flat_id,
                        "status": status or None,
                    },
                )
            )

        return apartments if apartments else None

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _slug(url)

        # Try to parse individual apartments
        apartments = self._parse_individual_apartments(html, url, ext_id)
        if apartments:
            return apartments

        tree = HTMLParser(html)

        h1 = tree.css_first("h1")
        title = h1.text(strip=True) if h1 else ""
        if not title:
            t = tree.css_first("title")
            title = t.text(strip=True) if t else ext_id

        desc_el = tree.css_first(".description, .content, article, .investment-description")
        description: str | None = None
        if desc_el:
            raw = desc_el.text(strip=True)
            description = raw if raw else None

        images: list[str] = []
        for img in tree.css("img[src]"):
            src = img.attributes.get("src", "")
            if src and not src.endswith(".svg"):
                images.append(_absolute_url(src))

        city = _city_from_url(url) or _city_from_text(title)

        if "/inwestycja/" in url:
            return []

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


register(PBGorskiScraper())
