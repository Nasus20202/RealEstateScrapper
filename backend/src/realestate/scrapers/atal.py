"""Atal.pl scraper — nationwide developer with Tricity investments, parses rendered DOM."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.districts import district_from_investment
from realestate.scrapers.helpers import fetch_json
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

# WordPress category IDs for cities
_CITY_CATEGORIES: dict[str, int] = {
    "gdansk": 887,
    "gdynia": 889,
    "sopot": 67,  # Sopot is part of Trójmiasto category
    "kowale": 7120,
    "reda": 893,
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
        """Discover investments via WordPress REST API instead of DOM."""
        city_key = ""
        if self._last_city:
            normalized = unicodedata.normalize("NFKD", self._last_city.strip().lower())
            city_key = normalized.encode("ascii", "ignore").decode("ascii")
            city_key = re.sub(r"\s+", "", city_key)

        cat_id = _CITY_CATEGORIES.get(city_key)
        if not cat_id:
            return []

        try:
            data = fetch_json(
                f"{_BASE_URL}/wp-json/wp/v2/investments"
                f"?categories={cat_id}&per_page=100&_fields=id,slug,title,link"
            )
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        listings: list[RawListing] = []
        for inv in data:
            slug = inv.get("slug", "")
            title = inv.get("title", {}).get("rendered", "") or slug
            link = inv.get("link", "")

            if link and "atal.pl" not in link:
                continue

            ext_id = slug
            inv_url = link or _absolute_url(f"/inwestycja/{slug}/")

            city = _city_from_text(title)
            if not city and self._last_city:
                city = self._last_city

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=inv_url,
                    title=title,
                    city=city,
                    district=district_from_investment(ext_id) or district_from_investment(title),
                    market="primary",
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
        """Attempt to parse individual apartments from an investment detail page.

        Returns a list of RawListing (one per apartment) or None if page is not
        an apartment listing page.
        """
        tree = HTMLParser(html)
        page_text = tree.body.text(strip=True) if tree.body else ""
        keywords = r"(?:mieszkanie|apartament|flat|cena|oferta|pokoj|metra|powierzchnia)"
        if not re.search(keywords, page_text[:5000], re.IGNORECASE):
            return None

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
            district=district_from_investment(ext_id) or district_from_investment(title),
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
        if price is None and area_m2 is None:
            return None
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
            district=district_from_investment(ext_id) or district_from_investment(title),
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

    def _parse_apartments_api(self, ext_id: str) -> list[RawListing] | None:
        try:
            rest_data = fetch_json(f"{_BASE_URL}/wp-json/wp/v2/investments?slug={ext_id}")
        except Exception:
            return None
        if not rest_data or not isinstance(rest_data, list) or not rest_data:
            return None
        inv_id = rest_data[0].get("id")
        if not inv_id:
            return None

        inv_data = rest_data[0]
        inv_name = inv_data.get("title", {}).get("rendered") or inv_data.get("slug") or ext_id

        # Resolve city from WordPress categories
        inv_cats = inv_data.get("categories", [])
        cat_to_city = {v: k for k, v in _CITY_CATEGORIES.items()}
        city = None
        for cat_id in inv_cats:
            cat_slug = cat_to_city.get(cat_id)
            if cat_slug == "sopot":
                city = "Sopot"
                break
            if cat_slug:
                city = _CITY_MAP.get(cat_slug)
                if city:
                    break

        # Fallback for Sopot/Trójmiasto: use last_city context
        if not city and self._last_city and self._last_city in ("Sopot", "Gdynia"):
            city = self._last_city
        if not city:
            city = _city_from_text(inv_name)

        try:
            ajax_body = fetch_json(
                f"{_BASE_URL}/wp-admin/admin-ajax.php",
                method="POST",
                form_data={
                    "action": "filter_apartments",
                    "investmentID": str(inv_id),
                    "searchType": "details",
                    "viewType": "tiles",
                    "hideclearfilters": "1",
                },
            )
        except Exception:
            return None

        if not isinstance(ajax_body, dict) or ajax_body.get("status") != "success":
            return None

        tile_html = ajax_body.get("html", "")
        if not tile_html:
            return None

        tree = HTMLParser(tile_html)
        tiles = tree.css("[data-ap-id]")
        if not tiles:
            return None

        if not city:
            city = _city_from_text(tile_html)
        if not city:
            city = _city_from_text(inv_name) or _city_from_text(ext_id)

        listings: list[RawListing] = []
        for tile in tiles:
            flat_id = tile.attributes.get("data-ap-id")
            if not flat_id:
                continue

            area_str = tile.attributes.get("data-area", "")
            area_m2 = float(area_str) if area_str else None
            rooms_str = tile.attributes.get("data-rooms", "")
            rooms = int(rooms_str) if rooms_str else None
            floor_str = tile.attributes.get("data-floor", "")
            floor_val = int(floor_str) if floor_str else None
            apt_name = tile.attributes.get("data-name", "")
            img_url = tile.attributes.get("data-image", "")
            link_url = tile.attributes.get("data-link", "")

            tile_text = tile.text(separator=" ", strip=True)
            # Find all prices and pick the largest (skipping per-m² prices)
            all_prices = re.findall(
                r"(?<![-\w/])(\d[\d\s\xa0]*(?:,\d+)?)\s*(?:zł|PLN)\b(?!\s*/\s*m)",
                tile_text,
                re.IGNORECASE,
            )
            price = None
            for raw in all_prices:
                cleaned = raw.replace("\xa0", "").replace(" ", "")
                cleaned = re.sub(r"[^\d,]", "", cleaned).replace(",", ".")
                if not cleaned:
                    continue
                try:
                    val = Decimal(cleaned)
                except InvalidOperation, ValueError:
                    continue
                if val >= 1000 and (price is None or val > price):
                    price = val

            status = ""
            status_el = tile.css_first(
                ".apartmentTile__basicData__item__badge, [class*=badge], [class*=status]"
            )
            if status_el:
                status = status_el.text(strip=True)

            images: list[str] = []
            if img_url:
                images.append(_absolute_url(img_url))

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{flat_id}",
                    url=_absolute_url(link_url) if link_url else "",
                    title=f"{inv_name} {apt_name}",
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    district=district_from_investment(ext_id) or district_from_investment(inv_name),
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": ext_id,
                        "flat_id": flat_id,
                        "status": _FLAT_STATUS_MAP.get(status.lower().strip(), status),
                    },
                )
            )

        return listings if listings else None

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)
        tree = HTMLParser(html)

        # Try API-based detail extraction first
        apartments = self._parse_apartments_api(ext_id)
        if apartments:
            return apartments

        # Try to parse individual apartments from DOM
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
            district=district_from_investment(ext_id) or district_from_investment(title),
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
