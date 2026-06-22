"""Invest Komfort scraper — Tricity developer (Gdańsk, Sopot, Gdynia)."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import (
    absolute_url,
    city_from_text,
    city_from_url,
    fetch_json,
    parse_area,
    parse_int_text,
    parse_money,
    parse_rooms,
    slug,
    slugify_city,
)
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://investkomfort.pl"
_SEARCH_API_URL = "https://ms.investkomfort.pl/indexes/property/search"
_SEARCH_API_TOKEN = "13e6e1f5d761c36e9f6472e0a1bd66c038dab65c2758ba382ae105ea9c8d03a7"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
}

_CITY_URL_SEGMENT: dict[str, str] = {
    "gdansk": "gdansk",
    "gdynia": "gdynia",
    "sopot": "sopot",
}

_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/pl",
        "/pl/cookie",
        "/pl/encyklopedia",
        "/pl/lokale-uslugowe",
        "/pl/polityka-prywatnosci",
        "/pl/ulubione",
        "/pl/wyszukaj-apartamenty",
        "/pl/wyszukiwarka",
    }
)


def _is_investment_link(href: str) -> bool:
    if not href:
        return False
    if href.startswith("tel:") or href.startswith("mailto:"):
        return False
    path = href.replace(_BASE_URL, "")
    if path in _EXCLUDED_PATHS:
        return False
    if "/apartamenty/" in path and path.count("/") >= 4:
        return True
    if "/inwestycj" in path.lower() or "/osiedl" in path.lower():
        return True
    return False


class InvestKomfortScraper:
    source_id = "invest-komfort"
    display_name = "Invest Komfort"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        city_segment = _CITY_URL_SEGMENT.get(criteria.city.lower().strip(), "gdansk")
        return f"{_BASE_URL}/pl/apartamenty/{city_segment}"

    def _parse_search_api(self, city_slug: str) -> list[RawListing]:
        payload = {
            "q": "",
            "filter": ["locale = pl", "type = apartment", f"city.slug = {city_slug}"],
            "sort": ["symbol:asc"],
            "hitsPerPage": 1000,
        }
        data = fetch_json(
            _SEARCH_API_URL,
            method="POST",
            payload=payload,
            headers={"Authorization": f"Bearer {_SEARCH_API_TOKEN}"},
        )
        hits = data.get("hits") if isinstance(data, dict) else []
        if not isinstance(hits, list):
            return []

        listings: list[RawListing] = []
        seen: set[str] = set()
        for item in hits:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("symbol") or item.get("propertyId") or item.get("id") or "")
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)

            investment = item.get("investment") if isinstance(item.get("investment"), dict) else {}
            phase = item.get("phase") if isinstance(item.get("phase"), dict) else {}
            city = item.get("city") if isinstance(item.get("city"), dict) else {}
            property_number = item.get("propertyNumber") or item.get("symbol") or external_id
            investment_name = investment.get("name") or "Invest Komfort"
            photo = item.get("photo")
            detail_url = str(item.get("yslabUrl") or item.get("card") or "")
            if not detail_url:
                detail_url = self.build_search_url(SearchCriteria(city=city_slug))

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=external_id,
                    url=detail_url,
                    title=f"{investment_name} {property_number}",
                    price=parse_money(str(item.get("totalPrice") or "")),
                    area_m2=parse_area(str(item.get("internalArea") or item.get("area") or "")),
                    rooms=int(item["rooms"]) if item.get("rooms") is not None else None,
                    floor=int(item["floorLevel"]) if item.get("floorLevel") is not None else None,
                    city=city.get("name") or _CITY_MAP.get(city_slug),
                    market="primary",
                    images=unique_listing_images([str(photo)] if photo else []),
                    attributes={
                        "investment": investment_name,
                        "investment_id": investment.get("id"),
                        "phase": phase.get("name"),
                        "phase_id": phase.get("id"),
                        "property_id": item.get("propertyId"),
                        "property_number": property_number,
                        "building_number": item.get("buildingNumber"),
                        "symbol": item.get("symbol"),
                        "price_per_m2": item.get("bundlePricePerSquareMeterUsable"),
                        "card_url": item.get("card"),
                        "params": [
                            p.get("name")
                            for p in item.get("propertyParams") or []
                            if isinstance(p, dict)
                        ],
                    },
                    raw=item,
                )
            )
        return listings

    def parse_search(self, html: str) -> list[RawListing]:
        if self._last_city:
            api_results = self._parse_search_api(slugify_city(self._last_city))
            if api_results:
                return api_results

        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            if not _is_investment_link(href):
                continue

            url = absolute_url(href.split("#")[0], _BASE_URL)
            if not url:
                continue

            ext_id = slug(url)
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            text = link.text(strip=True)
            if not text:
                text_el = link.css_first("h2, h3, h4, span")
                text = text_el.text(strip=True) if text_el else ext_id

            city = city_from_url(url, _CITY_MAP) or city_from_text(text, _CITY_MAP)
            if self._last_city and city:
                requested = city_from_text(self._last_city, _CITY_MAP) or self._last_city
                if requested.lower() not in city.lower():
                    continue

            card = link.parent if link.parent is not None else link
            card_text = card.text(separator=" ", strip=True) if card else text

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=url,
                    title=text,
                    price=parse_money(card_text),
                    area_m2=parse_area(card_text),
                    rooms=parse_rooms(card_text),
                    city=city,
                    market="primary",
                    attributes={"investment": ext_id, "investment_url": url},
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
        city = city_from_url(url, _CITY_MAP) or city_from_text(tree.html or "", _CITY_MAP)
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

            price = parse_money(card_text)
            area_m2 = parse_area(card_text)
            rooms = parse_rooms(card_text)
            floor_val = None
            floor_m = re.search(r"pi[eę]tro\s*(\d+)", card_text)
            if floor_m:
                floor_val = parse_int_text(floor_m.group(1))

            images: list[str] = []
            for img in card.css("img"):
                src = img.attributes.get("src", "")
                if src and not src.endswith(".svg"):
                    images.append(absolute_url(src, _BASE_URL))

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

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = slug(url)

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
                images.append(absolute_url(src, _BASE_URL))

        city = city_from_url(url, _CITY_MAP)

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


register(InvestKomfortScraper())
