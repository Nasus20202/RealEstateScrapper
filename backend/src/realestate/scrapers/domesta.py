"""Domesta.com.pl scraper — Tricity property developer, parses rendered DOM cards."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import fetch_json
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.domesta.com.pl"

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
    match = re.search(r"(?<![-\w])(\d[\d\s\xa0]*(?:,\d+)?)\s*zł", text, flags=re.IGNORECASE)
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


def _city_from_url(url: str) -> str | None:
    url_lower = url.lower()
    for key, name in _CITY_MAP.items():
        if f"/{key}" in url_lower or f"/{key}/" in url_lower:
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


class DomestaScraper:
    source_id = "domesta"
    display_name = "Domesta"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return f"{_BASE_URL}/"

    def parse_search(self, html: str) -> list[RawListing]:
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for link in tree.css('a[href*="/gdansk/"], a[href*="/gdynia/"], a[href*="/sopot/"]'):
            href = link.attributes.get("href", "")
            if not href or href.startswith("tel:") or href.startswith("mailto:"):
                continue

            url = _absolute_url(href.split("#")[0])
            ext_id = _investment_from_url(url)
            if not ext_id:
                continue

            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            text = link.text(strip=True)
            if not text:
                h3 = link.css_first("h3, h2")
                text = h3.text(strip=True) if h3 else ext_id

            city = _city_from_url(url) or _city_from_text(text)

            if self._last_city:
                requested = _city_from_text(self._last_city) or self._last_city
                if city and requested.lower() not in city.lower():
                    continue

            card = link
            card_text = card.text(separator=" ", strip=True)
            price_per_m2 = _money(card_text)

            address_el = card.css_first("p.h300, p.text-gray80")
            street_text = address_el.text(strip=True) if address_el else None
            street = None
            if street_text and city:
                street = street_text.replace(city, "").strip(" ,") or None

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=url,
                    title=text or ext_id.replace("-", " ").title(),
                    price=price_per_m2,
                    city=city,
                    street=street,
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
        homer = self._parse_homer_apartments(tree, url, ext_id)
        if homer:
            return homer
        page_text = tree.body.text(strip=True) if tree.body else ""
        city = _city_from_text(page_text)
        apartments: list[RawListing] = []

        for card in tree.css(
            "[class*=flat], [class*=apartment], [class*=offer], "
            "[class*=mieszkanie], [class*=listing-card], [class*=card], "
            "[data-id], [class*=property]"
        ):
            card_text = card.text(separator=" ", strip=True)
            if len(card_text) < 15:
                continue

            flat_id = card.attributes.get("data-id") or card.attributes.get("data-flat-id")
            if not flat_id:
                id_match = re.search(r"(\d+)\s*(?:m²|m2|zł)", card_text[:50])
                flat_id = id_match.group(1) if id_match else str(abs(hash(card_text)) % 100000)

            title_el = card.css_first("h2, h3, h4, [class*=title], [class*=name]")
            title = title_el.text(strip=True) if title_el else f"Mieszkanie {flat_id}"

            price = _money(card_text)
            area_m2 = _area(card_text)
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

    def _parse_homer_apartments(self, tree: HTMLParser, url: str, ext_id: str) -> list[RawListing]:
        iframe = tree.css_first('iframe[id^="homerweb-"]')
        if iframe is None:
            return []
        investment_id = iframe.attributes.get("id", "").replace("homerweb-", "")
        if not investment_id:
            return []
        try:
            config = fetch_json(
                f"https://ehomer.pl/api/v3/get-web-config?investmentId={investment_id}"
            )
            response = config.get("response") if isinstance(config, dict) else {}
            api_url = response.get("apiUrl") if isinstance(response, dict) else None
            investment_name = response.get("name") if isinstance(response, dict) else ext_id
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

        if url and any(segment in url for segment in ("/gdansk/", "/gdynia/", "/sopot/")):
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


register(DomestaScraper())
