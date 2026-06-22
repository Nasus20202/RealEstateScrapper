"""Atal.pl scraper — nationwide developer with Tricity investments, parses rendered DOM."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://atal.pl"

_FLAT_STATUS_MAP = {
    "dostepne": "available",
    "dostępne": "available",
    "wolne": "available",
    "zarezerwowane": "reserved",
    "sprzedane": "sold",
}

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "kowale": "Kowale",
    "reda": "Reda",
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


class AtalScraper:
    source_id = "atal"
    display_name = "Atal"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return f"{_BASE_URL}/"

    def parse_search(self, html: str) -> list[RawListing]:
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in tree.css(
            ".investmentBox, [class*=investmentBox], "
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

            street = None

            price_val = _money(card_text)
            if price_val is not None and price_val < 1000:
                price_val = None

            area_val = _area(card_text)
            rooms_val = _rooms(card_text)

            avail_match = re.search(r"Dost[pę]ne mieszkania:\s*(\d+)", card_text)
            available = int(avail_match.group(1)) if avail_match else None

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            attributes: dict = {"investment": ext_id}
            if available is not None:
                attributes["available_units"] = available

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
                    street=street,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes=attributes,
                )
            )

        return listings

    def _parse_individual_apartments(
        self,
        html: str,
        url: str,
        ext_id: str,
    ) -> list[RawListing] | None:
        """Attempt to parse individual apartments from an investment detail page.

        Returns a list of RawListing (one per apartment) or None if page is not
        an apartment listing page.
        """
        tree = HTMLParser(html)
        page_text = tree.body.text(strip=True) if tree.body else ""

        apartments: list[RawListing] = []
        city = _city_from_text(page_text)
        street = None

        # Try JSON-LD structured data or embedded JSON first
        for script in tree.css("script"):
            raw = script.text(strip=True)
            if not raw:
                continue
            # Look for embedded apartment data in window.__INITIAL_STATE__ or similar
            if (
                "mieszkania" in raw
                and "id" in raw
                and ("cena" in raw or "price" in raw or "pietro" in raw)
            ):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError, ValueError:
                    continue
                if isinstance(data, list):
                    for item in data:
                        flat = self._flat_from_dict(item, ext_id, city, street, url)
                        if flat:
                            apartments.append(flat)
                    if apartments:
                        return apartments
                elif isinstance(data, dict):
                    flats_data = _find_list_of_flats(data)
                    if flats_data:
                        for item in flats_data:
                            flat = self._flat_from_dict(item, ext_id, city, street, url)
                            if flat:
                                apartments.append(flat)
                        if apartments:
                            return apartments

        # Try DOM-based apartment card parsing
        for card in tree.css(
            "[class*=-flat], [class*=-apartment], [class*=-mieszkanie], "
            ".flat-card, .apartment-card, [class*=offer-card], [class*=property-card], "
            "[class*=listing-card], [data-flat-id], [data-apartment-id]"
        ):
            flat = self._flat_from_card(card, ext_id, city, street, url)
            if flat:
                apartments.append(flat)

        if apartments:
            return apartments

        # Try to find a JSON data URL in the page and return None
        # so the caller knows to use the investment-level fallback
        return None

    def _flat_from_dict(
        self, item: dict, ext_id: str, city: str | None, street: str | None, url: str = ""
    ) -> RawListing | None:
        flat_id = (
            item.get("id") or item.get("ID") or item.get("flat_id") or item.get("mieszkanie_id")
        )
        if flat_id is None:
            return None
        flat_id = str(flat_id)

        title = str(
            item.get("title") or item.get("name") or item.get("nazwa") or f"Mieszkanie {flat_id}"
        )
        price = _money(str(item.get("cena") or item.get("price") or item.get("cena_brutto") or ""))
        area_m2 = _area(
            str(item.get("powierzchnia") or item.get("area") or item.get("metraz") or "")
        )
        rooms = _rooms(item.get("pokoje") or item.get("rooms") or item.get("liczba_pokoi") or "")
        floor_val = _int(item.get("pietro") or item.get("floor") or item.get("numer_pietra"))

        img_urls: list[str] = []
        raw_images = (
            item.get("zdjecia")
            or item.get("images")
            or item.get("galeria")
            or item.get("gallery")
            or []
        )
        if isinstance(raw_images, list):
            for img in raw_images:
                if isinstance(img, str):
                    img_urls.append(_absolute_url(img))
                elif isinstance(img, dict):
                    for key in ("url", "src", "m_img_500", "m_img_750", "full"):
                        val = img.get(key) or ""
                        if val:
                            img_urls.append(_absolute_url(val))
                            break

        status = item.get("status") or item.get("dostepnosc") or ""
        status_normalized = _FLAT_STATUS_MAP.get(status.lower().strip(), status)

        return RawListing(
            source_id=self.source_id,
            external_id=f"{ext_id}-{flat_id}",
            url=url,
            title=title,
            price=price,
            area_m2=area_m2,
            rooms=rooms,
            floor=floor_val,
            city=city,
            street=street,
            description=item.get("opis") or item.get("description") or None,
            market="primary",
            images=unique_listing_images(img_urls),
            attributes={
                "investment": ext_id,
                "flat_id": flat_id,
                "status": status_normalized,
                "floor": floor_val,
            },
        )

    def _flat_from_card(
        self, card, ext_id: str, city: str | None, street: str | None, url: str = ""
    ) -> RawListing | None:
        card_text = card.text(separator=" ", strip=True)
        flat_id = (
            card.attributes.get("data-flat-id")
            or card.attributes.get("data-apartment-id")
            or card.attributes.get("data-id")
        )
        name_el = card.css_first("h2, h3, h4, [class*=title], [class*=name]")
        title = name_el.text(strip=True) if name_el else (flat_id or "Mieszkanie")

        if not flat_id:
            slugs = re.findall(r"(\d+)$", title)
            flat_id = slugs[0] if slugs else str(hash(card_text))

        price = _money(card_text)
        area_m2 = _area(card_text)
        rooms = _rooms(card_text)
        floor_val = None
        floor_match = re.search(r"pi[eę]tro\s*(\d+)", card_text)
        if floor_match:
            floor_val = _int(floor_match.group(1))

        status_el = card.css_first("[class*=status], [class*=availability], [class*=dostepnosc]")
        status = status_el.text(strip=True) if status_el else ""

        images: list[str] = []
        for img in card.css("img"):
            src = _image_url(img)
            if src and not src.endswith(".svg") and src not in images:
                images.append(src)

        return RawListing(
            source_id=self.source_id,
            external_id=f"{ext_id}-{flat_id}",
            url=url,
            title=title,
            price=price,
            area_m2=area_m2,
            rooms=rooms,
            floor=floor_val,
            city=city,
            street=street,
            market="primary",
            images=unique_listing_images(images),
            attributes={
                "investment": ext_id,
                "flat_id": flat_id,
                "status": _FLAT_STATUS_MAP.get(status.lower().strip(), status),
                "floor": floor_val,
            },
        )

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)
        tree = HTMLParser(html)

        # Try to parse individual apartments first
        apartments = self._parse_individual_apartments(html, url, ext_id)
        if apartments:
            return apartments

        # Fallback: return investment-level detail
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
        street = None

        return RawListing(
            source_id=self.source_id,
            external_id=ext_id,
            url=url,
            title=title,
            description=description,
            images=images,
            city=city,
            street=street,
            market="primary",
        )


def _find_list_of_flats(data: dict) -> list[dict] | None:
    """Recursively search for a list of flat/apartment dictionaries in nested JSON."""
    for _key, value in data.items():
        if isinstance(value, list) and value:
            if isinstance(value[0], dict):
                sample = value[0]
                flat_keys = {
                    "cena",
                    "price",
                    "pokoje",
                    "rooms",
                    "metraz",
                    "area",
                    "pietro",
                    "floor",
                }
                if flat_keys & set(str(k).lower() for k in sample.keys()):
                    return value
        elif isinstance(value, dict):
            result = _find_list_of_flats(value)
            if result:
                return result
    return None


register(AtalScraper())
