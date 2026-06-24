"""Develia.pl scraper — nationwide developer, parses rendered DOM cards."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import fetch_json
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.develia.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
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


class DeveliaScraper:
    source_id = "develia"
    display_name = "Develia"

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
            return f"{_BASE_URL}/mieszkania/{city_slug}"
        return f"{_BASE_URL}/mieszkania"

    def parse_search(self, html: str) -> list[RawListing]:
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in tree.css(
            ".investment-box, [class*=investment-box], "
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

            avail_match = re.search(r"Wolne mieszkania:\s*(\d+)", card_text)
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
                    url=url or f"{_BASE_URL}/mieszkania",
                    title=text,
                    price=price_val,
                    area_m2=area_val,
                    rooms=rooms_val,
                    city=city,
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
        """Parse individual apartment cards from a Develia investment detail page."""
        tree = HTMLParser(html)
        homer = self._parse_homer_apartments(tree, url, ext_id)
        if homer:
            return homer
        page_text = tree.body.text(strip=True) if tree.body else ""
        city = _city_from_text(page_text)

        apartments: list[RawListing] = []

        for card in tree.css(
            "[class*=-flat], [class*=-apartment], [class*=offer-card], "
            "[class*=property-card], [class*=listing-item], [class*=apartment-item], "
            "[class*=mieszkanie-card], [data-id], [class*=investment-item]"
        ):
            card_text = card.text(separator=" ", strip=True)

            # Skip navigation/non-apartment elements
            lowered = card_text.lower()
            if (
                len(card_text) < 10
                or "zobacz" in lowered
                or "zostaw nam kontakt" in lowered
                or "kontakt do siebie" in lowered
            ):
                continue

            flat_id = (
                card.attributes.get("data-id")
                or card.attributes.get("data-flat-id")
                or card.attributes.get("data-apartment-id")
            )
            if not flat_id:
                num_match = re.search(r"Mieszkanie\s*(\d+)", card_text, re.IGNORECASE)
                flat_id = num_match.group(1) if num_match else str(hash(card_text))

            title_el = card.css_first("h2, h3, h4, [class*=title], [class*=name]")
            title = title_el.text(strip=True) if title_el else f"Mieszkanie {flat_id}"

            price = _money(card_text)
            area_m2 = _area(card_text)
            rooms = _rooms(card_text)

            floor_val = None
            floor_match = re.search(r"pi[eę]tro\s*(\d+)", card_text)
            if floor_match:
                floor_val = _int(floor_match.group(1))
            total_floors_val = None
            total_floor_match = re.search(r"pi[eę]tro\s*\d+/(\d+)", card_text)
            if total_floor_match:
                total_floors_val = _int(total_floor_match.group(1))
            if "parter" in card_text.lower():
                floor_val = 0

            if price is None and area_m2 is None and rooms is None and floor_val is None:
                continue

            status = ""
            status_el = card.css_first("[class*=status], [class*=dostepnosc]")
            if status_el:
                status = status_el.text(strip=True)

            description_el = card.css_first("p, [class*=desc], [class*=opis]")
            description = description_el.text(strip=True) if description_el else None

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
                    total_floors=total_floors_val,
                    city=city,
                    market="primary",
                    description=description,
                    images=unique_listing_images(images),
                    attributes={
                        "investment": ext_id,
                        "flat_id": flat_id,
                        "status": status,
                    },
                )
            )

        return apartments if apartments else None

    def _parse_homer_apartments(self, tree: HTMLParser, url: str, ext_id: str) -> list[RawListing]:
        html = tree.html or ""
        match = re.search(r"Odyssey\.init\([^)]*id:\s*['\"]([^'\"]+)['\"]", html)
        if not match:
            return []
        code = match.group(1)
        try:
            config = fetch_json(f"https://ehomer.pl/api/v3/get-web-config?investmentId={code}")
            response = config.get("response") if isinstance(config, dict) else {}
            api_url = response.get("apiUrl") if isinstance(response, dict) else None
            investment_name = response.get("name") if isinstance(response, dict) else ext_id
            investment_id = response.get("investmentId") if isinstance(response, dict) else code
            payload = fetch_json(api_url) if api_url else {}
        except Exception:
            return []
        flats = payload.get("items") if isinstance(payload, dict) else []
        if not flats and isinstance(payload, dict):
            flats = payload.get("response")
        if not isinstance(flats, list):
            return []
        city = _city_from_text(tree.html or "") or _city_from_text(url)
        listings: list[RawListing] = []
        for item in flats:
            if not isinstance(item, dict):
                continue
            system_id = str(item.get("system_id") or item.get("foreignId") or item.get("id") or "")
            if not system_id:
                continue
            images: list[str] = []
            images.extend(str(img) for img in item.get("pdf_img") or [] if img)
            for plan in item.get("floor_plans") or []:
                if isinstance(plan, dict):
                    images.extend(
                        str(plan.get(k)) for k in ("thumb_x2", "thumb", "url") if plan.get(k)
                    )
            price_val = item.get("price")
            if price_val is None or price_val == 0:
                price_val = item.get("promo_price")
            price = Decimal(str(price_val)) if price_val else None
            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{investment_id}-{system_id}",
                    url=str(item.get("websiteUrl") or url),
                    title=f"{investment_name} {item.get('name') or system_id}",
                    price=price,
                    area_m2=_float(item.get("area")),
                    rooms=int(item["num_rooms"]) if item.get("num_rooms") is not None else None,
                    floor=int(item["floor"]) if item.get("floor") is not None else None,
                    city=city,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": investment_name,
                        "investment_id": investment_id,
                        "homer_code": code,
                        "homer_id": item.get("id"),
                        "system_id": item.get("system_id"),
                        "foreign_id": item.get("foreignId"),
                        "availability": item.get("availability"),
                        "price_sqm": item.get("price_sqm"),
                        "extras": item.get("extras") or [],
                        "pdf": item.get("pdf"),
                    },
                    raw=item,
                )
            )
        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)

        # Try to parse individual apartments
        apartments = self._parse_individual_apartments(html, url, ext_id)
        if apartments:
            return apartments

        return []


register(DeveliaScraper())
