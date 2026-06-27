"""Allcon scraper — Tricity developer (Gdynia, Gdańsk, Łeba)."""

from __future__ import annotations

import json
import re

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.districts import district_from_investment
from realestate.scrapers.helpers import (
    absolute_url,
    add_query_params,
    city_from_text,
    city_from_url,
    fetch_json,
    fetch_text,
    parse_area,
    parse_money,
    parse_rooms,
    slug,
    slugify_city,
)
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.allcon.pl"
_API_BASE = "https://panel.allcon.pl/api/v1"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "leba": "Łeba",
    "łeba": "Łeba",
}

_CITY_URL_SEGMENT: dict[str, str] = {
    "gdansk": "gdansk",
    "gdynia": "gdynia",
    "leba": "leba",
    "łeba": "leba",
}

_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/aktualnosci",
        "/kontakt",
        "/o-nas",
        "/polityka-prywatnosci",
        "/regulamin-06-2026",
        "/spolki-allcon",
        "/ulubione",
        "/wynajem-nieruchomosci",
        "/generalne-wykonawstwo",
        "/kupimy-grunty",
        "/strona-glowna/prospekty",
        "/strona-glowna/kontakt-inspektor-ochrony-danych",
    }
)


def _is_investment_link(href: str) -> bool:
    if not href:
        return False
    if href.startswith("tel:") or href.startswith("mailto:"):
        return False
    if href.startswith("/aktualnosci"):
        return False
    path = href.replace(_BASE_URL, "")
    if path in _EXCLUDED_PATHS:
        return False
    if path.startswith("/") and path.count("/") >= 2:
        slug = path.rstrip("/").split("/")[-1]
        if slug and slug not in ("", "aktualnosci", "kontakt", "o-nas"):
            return True
    if "/inwestycj" in path.lower() or "/osiedl" in path.lower():
        return True
    return False


class AllconScraper:
    source_id = "allcon"
    display_name = "Allcon"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def _api_url_for_investment(self, investment_slug: str) -> str:
        """Construct the Allcon API URL for a specific investment."""
        return f"{_API_BASE}/investment/local?slug={investment_slug}"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        city_segment = _CITY_URL_SEGMENT.get(slugify_city(criteria.city), "gdynia")
        return f"{_BASE_URL}/{city_segment}"

    def _parse_resimo_configs(self, html: str) -> list[RawListing]:
        app_urls = [
            f"https://allinone.prod.resimo.io/allcon/{app_slug}/"
            for app_slug in sorted(
                set(re.findall(r"allinone\.prod\.resimo\.io/allcon/([^/'\"?#\\]+)", html))
            )
        ]
        listings: list[RawListing] = []
        seen: set[str] = set()
        for app_url in app_urls:
            app_url = app_url.rstrip("/") + "/"
            inv_slug = slug(app_url)
            try:
                app_html = fetch_text(app_url)
            except Exception:
                continue
            api_match = re.search(r"url:\s*['\"]([^'\"]+/apartments/?)['\"]", app_html)
            token_match = re.search(r"token:\s*['\"]([^'\"]+)['\"]", app_html)
            if not api_match or not token_match:
                continue
            buildings = re.findall(r"buildingList:\s*\[([^\]]*)\]", app_html)
            building_list = ""
            if buildings:
                building_list = ";".join(re.findall(r"['\"]([^'\"]+)['\"]", buildings[0]))
            fields_match = re.search(r"additionalFields:\s*\[([^\]]*)\]", app_html)
            additional_fields = ""
            if fields_match:
                additional_fields = ",".join(
                    re.findall(r"['\"]([^'\"]+)['\"]", fields_match.group(1))
                )
            params = {"token": token_match.group(1)}
            if building_list:
                params["building_list"] = building_list
            if additional_fields:
                params["additional_fields"] = additional_fields
            try:
                payload = fetch_json(
                    add_query_params(api_match.group(1), params),
                    headers={"Origin": "https://allinone.prod.resimo.io", "Referer": app_url},
                )
            except Exception:
                continue
            city = None
            for city_key, city_name in _CITY_MAP.items():
                if city_key in inv_slug:
                    city = city_name
                    break
            if city is None and self._last_city:
                city = city_from_text(self._last_city, _CITY_MAP) or self._last_city
            if self._last_city:
                requested = city_from_text(self._last_city, _CITY_MAP) or self._last_city
                if city and requested.lower() not in city.lower():
                    continue
            for building in payload if isinstance(payload, list) else []:
                apartments = building.get("apartments") if isinstance(building, dict) else None
                if not isinstance(apartments, list):
                    continue
                for apt in apartments:
                    if not isinstance(apt, dict) or apt.get("id") is None:
                        continue
                    apt_id = str(apt["id"])
                    ext_id = f"{inv_slug}-{apt_id}"
                    if ext_id in seen:
                        continue
                    seen.add(ext_id)
                    name = str(apt.get("name") or apt.get("mappingName") or apt_id)
                    projection_url = (
                        f"{_BASE_URL}/api/investment/{inv_slug}/local/{name}/projection-download"
                    )
                    listings.append(
                        RawListing(
                            source_id=self.source_id,
                            external_id=ext_id,
                            url=f"{_BASE_URL}/{inv_slug}/oferta/{name}",
                            title=f"{inv_slug.replace('-', ' ').title()} {name}",
                            price=parse_money(str(apt.get("price") or "")),
                            area_m2=parse_area(str(apt.get("area") or "")),
                            rooms=int(apt["rooms"]) if apt.get("rooms") is not None else None,
                            floor=int(apt["floor"]) if apt.get("floor") is not None else None,
                            city=city,
                            district=district_from_investment(inv_slug),
                            market="primary",
                            attributes={
                                "investment": inv_slug,
                                "building": apt.get("buildingNumber"),
                                "status": apt.get("status"),
                                "price_per_m2": apt.get("pricePerSquareMeter"),
                                "projection_download_url": projection_url,
                            },
                            raw=apt,
                        )
                    )
        return listings

    def parse_search(self, html: str) -> list[RawListing]:
        api_listings = self._parse_resimo_configs(html)
        if api_listings:
            return api_listings

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
                text_el = link.css_first("h2, h3, h4, span, p")
                text = text_el.text(strip=True) if text_el else ext_id

            city = city_from_url(url, _CITY_MAP) or city_from_text(text, _CITY_MAP)
            if self._last_city and city:
                requested = city_from_text(self._last_city, _CITY_MAP) or self._last_city
                if requested.lower() not in city.lower():
                    continue

            card = link.parent if link.parent is not None else link
            card_text = card.text(separator=" ", strip=True) if card else text

            # Store the API URL as the main URL for detail fetching
            api_url = self._api_url_for_investment(ext_id)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=api_url,
                    title=text,
                    price=parse_money(card_text),
                    area_m2=parse_area(card_text),
                    rooms=parse_rooms(card_text),
                    city=city,
                    district=district_from_investment(ext_id) or district_from_investment(text),
                    market="primary",
                    attributes={"investment": ext_id, "investment_url": url},
                )
            )

        if not listings:
            import json as _json

            for script in tree.css("script"):
                raw = script.text(strip=True)
                if not raw or "initialFilters" not in raw:
                    continue
                try:
                    data = _json.loads(raw)
                except _json.JSONDecodeError:
                    continue
                filters = data.get("initialFilters", {})
                investments = filters.get("investments", {})
                for inv_slug, name in investments.items():
                    if inv_slug in seen_ids:
                        continue
                    seen_ids.add(inv_slug)
                    city_slug = ""
                    for cs in _CITY_MAP:
                        if cs in inv_slug:
                            city_slug = cs
                            break
                    inv_url = f"{_BASE_URL}/{inv_slug}"
                    if city_slug:
                        inv_url = f"{_BASE_URL}/{city_slug}/{inv_slug}"
                    api_url = self._api_url_for_investment(inv_slug)
                    listings.append(
                        RawListing(
                            source_id=self.source_id,
                            external_id=inv_slug,
                            url=api_url,
                            title=name,
                            city=_CITY_MAP.get(city_slug),
                            district=(
                                district_from_investment(inv_slug) or district_from_investment(name)
                            ),
                            market="primary",
                            attributes={"investment": inv_slug, "investment_url": inv_url},
                        )
                    )
                break

        return listings

    def _parse_apartments_api(self, body: str, url: str) -> list[RawListing]:
        """Parse the Allcon REST API response into individual apartment listings."""
        raw_body = body.strip()
        if raw_body.startswith("{"):
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                return []
        else:
            tree = HTMLParser(body)
            raw_body = tree.body.text(strip=True) if tree.body else raw_body
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                return []

        if isinstance(payload, dict):
            data = (
                payload.get("data")
                or payload.get("apartments")
                or payload.get("flats")
                or payload.get("items")
                or payload.get("results")
                or []
            )
            investment_name = payload.get("name") or payload.get("investment_name") or ""
        elif isinstance(payload, list):
            data = payload
            investment_name = ""
        else:
            return []

        if not isinstance(data, list):
            return []

        ext_id = slug(url)
        city = city_from_url(url, _CITY_MAP) or city_from_text(investment_name, _CITY_MAP)
        listings: list[RawListing] = []

        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("ID") or item.get("number")
            if item_id is None:
                continue
            item_id = str(item_id)

            title = str(item.get("name") or item.get("title") or f"Mieszkanie {item_id}")

            price = parse_money(
                str(item.get("price") or item.get("cena") or item.get("priceGross") or "")
            )
            if price is None:
                price = parse_money(str(item.get("omnibusPrice") or ""))

            area_m2 = parse_area(
                str(item.get("area") or item.get("powierzchnia") or item.get("areaUsable") or "")
            )
            rooms = parse_rooms(str(item.get("rooms") or item.get("pokoje") or ""))
            floor_val = None
            floor_raw = item.get("floor") or item.get("pietro")
            if floor_raw is not None:
                try:
                    floor_val = int(floor_raw)
                except TypeError, ValueError:
                    pass

            status = item.get("status") or item.get("dostepnosc") or ""

            images: list[str] = []
            for img_key in ("images", "zdjecia", "photos", "gallery", "galeria"):
                raw_images = item.get(img_key, [])
                if isinstance(raw_images, list):
                    for img in raw_images:
                        if isinstance(img, str):
                            images.append(absolute_url(img, _BASE_URL))
                        elif isinstance(img, dict):
                            for attr in ("url", "src", "full", "thumb", "medium"):
                                val = img.get(attr) or ""
                                if val:
                                    images.append(absolute_url(val, _BASE_URL))
                                    break

            attributes: dict = {
                "investment": ext_id,
                "flat_id": item_id,
                "status": status,
            }
            for extra in (
                "building",
                "availability",
                "status_label",
                "price_per_usable_m2",
                "priceNet",
                "priceNetm2",
                "priceGrossm2",
                "omnibusPrice",
            ):
                val = item.get(extra)
                if val is not None:
                    attributes[extra] = val

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{item_id}",
                    url=f"{_BASE_URL}/",
                    title=title,
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    district=(
                        district_from_investment(ext_id)
                        or district_from_investment(investment_name)
                    ),
                    market="primary",
                    images=unique_listing_images(images),
                    description=item.get("description") or item.get("opis") or None,
                    attributes=attributes,
                    raw=item,
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        if "/api/v1/" in url or "panel.allcon.pl" in url:
            apartments = self._parse_apartments_api(html, url)
            if apartments:
                return apartments

        ext_id = slug(url)
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
            district=district_from_investment(ext_id) or district_from_investment(title),
            market="primary",
        )


register(AllconScraper())
