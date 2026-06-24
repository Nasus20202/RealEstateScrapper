"""Euro Styl scraper — Tricity developer (part of Dom Development Group).

Uses the /iapi/search/search API which returns all flats inline across
all investments (no pagination).  No per‑flat prices are exposed.
"""

from __future__ import annotations

import re
from decimal import Decimal

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import (
    absolute_url,
    fetch_json,
    parse_area,
    parse_rooms,
)

_BASE_URL = "https://www.eurostyl.com.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
    "rumia": "Rumia",
}


def _ascii_fold(text: str) -> str:
    result = text.lower().replace("ł", "l").replace("ń", "n")
    result = result.replace("ą", "a").replace("ę", "e")
    result = result.replace("ó", "o").replace("ś", "s")
    result = result.replace("ć", "c").replace("ź", "z").replace("ż", "z")
    return result


def _city_slug(city: str) -> str:
    return _ascii_fold(city.strip())


def _parse_floor(text: str) -> int | None:
    """Parse '6 <span>piętro</span>' or 'parter' to int."""
    if not text:
        return None
    cleaned = re.sub(r"<[^>]+>", "", text).strip().lower()
    if cleaned == "parter":
        return 0
    m = re.search(r"(\d+)", cleaned)
    return int(m.group(1)) if m else None


def _parse_price(price_obj: dict) -> Decimal | None:
    """Try to extract a price from the API price object."""
    for key in ("new", "old", "value", "gross", "net"):
        val = price_obj.get(key)
        if val is not None:
            try:
                return Decimal(str(val))
            except Exception:
                pass
    return None


class EuroStylScraper:
    source_id = "euro-styl"
    display_name = "Euro Styl"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return (
            f"{_BASE_URL}/pl-pl/trojmiasto/"
            "wyniki-wyszukiwania-mieszkania"
            "?city=trojmiasto&language=pl-pl&type=mk&viewType=tiles"
        )

    def parse_search(self, html: str) -> list[RawListing]:
        payload = fetch_json(
            f"{_BASE_URL}/iapi/search/search?city=trojmiasto&language=pl-pl&type=mk&viewType=table"
        )
        if not isinstance(payload, dict):
            return []

        raw_investments = payload.get("investments")
        if not isinstance(raw_investments, list):
            return []

        requested_slug = _city_slug(self._last_city) if self._last_city else ""
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for inv in raw_investments:
            if not isinstance(inv, dict):
                continue
            inv_name = inv.get("name", "")
            city = inv.get("city", "")
            district = inv.get("district", "")
            street = inv.get("street", "")
            inv_id = inv.get("id", "")

            if requested_slug:
                city_slug = _city_slug(city)
                if requested_slug not in city_slug:
                    continue

            raw_flats = inv.get("flats")
            if not isinstance(raw_flats, list):
                continue

            for flat in raw_flats:
                if not isinstance(flat, dict):
                    continue
                flat_id = flat.get("id", "")
                if not flat_id or flat_id == "search_help_box":
                    continue

                number = flat.get("flat", "")
                area_raw = flat.get("area", "")
                area_m2 = _parse_area_html(area_raw) if area_raw else None
                rooms_raw = flat.get("rooms", "")
                rooms = parse_rooms(rooms_raw) if rooms_raw else None
                floor_raw = flat.get("floor", "")
                floor_val = _parse_floor(floor_raw) if floor_raw else None

                price_obj = flat.get("price", {}) or {}
                price = _parse_price(price_obj) if isinstance(price_obj, dict) else None

                ext_id = f"{inv_id}-{flat_id}" if inv_id and flat_id else f"{inv_name}-{number}"
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                title = f"{inv_name} {number}".strip()

                img_url = ""
                picture = flat.get("picture", {}) or {}
                if isinstance(picture, dict):
                    img_url = picture.get("img", "") or ""

                listings.append(
                    RawListing(
                        source_id=self.source_id,
                        external_id=ext_id,
                        url=f"{_BASE_URL}/",
                        title=title,
                        price=price,
                        area_m2=area_m2,
                        rooms=rooms,
                        floor=floor_val,
                        city=city or None,
                        district=district or None,
                        street=street or None,
                        market="primary",
                        images=[absolute_url(img_url, _BASE_URL)] if img_url else [],
                        attributes={
                            "investment": inv_name,
                            "flat_id": flat_id,
                        },
                    )
                )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        return []


def _parse_area_html(text: str) -> float | None:
    """Parse '122,64 m<sup>2</sup>' to float."""
    cleaned = re.sub(r"<[^>]+>", "", text).strip()
    return parse_area(cleaned)


register(EuroStylScraper())
