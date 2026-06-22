"""Euro Styl scraper — Tricity developer (part of Dom Development Group)."""

from __future__ import annotations

import json
import re

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import (
    absolute_url,
    city_from_text,
    city_from_url,
    fetch_text,
    parse_area,
    parse_floor,
    parse_money,
    parse_rooms,
    slug,
)
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.eurostyl.com.pl"
_INVESTMENTS_URL = f"{_BASE_URL}/pl-pl/trojmiasto/lista-inwestycji"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
    "rumia": "Rumia",
}

_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/pl-pl/trojmiasto",
        "/pl-pl/trojmiasto/esg",
        "/pl-pl/trojmiasto/kontakt",
        "/pl-pl/trojmiasto/aktualnosci",
        "/pl-pl/trojmiasto/kredyty",
        "/pl-pl/trojmiasto/aranzacja-wnetrz",
        "/pl-pl/trojmiasto/nasze-realizacje",
        "/pl-pl/trojmiasto/o-nas",
        "/pl-pl/trojmiasto/polityka-prywatnosci",
        "/pl-pl/trojmiasto/regulamin",
        "/pl-pl/trojmiasto/cookies",
        "/pl-pl/trojmiasto/komunikat-bezpieczenstwa",
        "/pl-pl/trojmiasto/biuro-prasowe",
        "/pl-pl/trojmiasto/informacja-o-strategii-podatkowej",
        "/pl-pl/trojmiasto/euro-styl-construction",
        "/pl-pl/trojmiasto/zakupimy-grunty",
        "/pl-pl/trojmiasto/kariera",
        "/pl-pl/trojmiasto/strefa-akcjonariusza",
        "/pl-pl/trojmiasto/oferty-specjalne",
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
    if "/lista-inwestycji/" in path and path.count("/") >= 4:
        url_slug = path.rstrip("/").split("/")[-1]
        if url_slug and url_slug not in ("", "lista-inwestycji"):
            return True
    return False


class EuroStylScraper:
    source_id = "euro-styl"
    display_name = "Euro Styl"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def _api_url_for_investment(self, investment_slug: str) -> str:
        return f"{_BASE_URL}/iapi/search/single?slug={investment_slug}"

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return _INVESTMENTS_URL

    def parse_search(self, html: str) -> list[RawListing]:
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
                    market="primary",
                    attributes={"investment": ext_id, "investment_url": url},
                )
            )

        if listings:
            return listings
        if "eurostyl" not in html.lower() and "euro styl" not in html.lower():
            return []
        return self._parse_sitemap_flats()

    def _parse_sitemap_flats(self) -> list[RawListing]:
        try:
            sitemap = fetch_text(f"{_BASE_URL}/sitemap.xml")
        except Exception:
            return []
        urls = sorted(
            set(
                re.findall(
                    r"https://www\.eurostyl\.com\.pl/pl-pl/trojmiasto/mieszkanie\?id=[^<\s]+",
                    sitemap,
                )
            )
        )
        listings: list[RawListing] = []
        for flat_url in urls[:300]:
            try:
                html = fetch_text(flat_url)
            except Exception:
                continue
            listing = self._parse_flat_page(html, flat_url)
            if listing:
                listings.append(listing)
        return listings

    def _parse_flat_page(self, html: str, url: str) -> RawListing | None:
        tree = HTMLParser(html)
        query_id_match = re.search(r"[?&]id=([^&]+)", url)
        external_id = query_id_match.group(1) if query_id_match else slug(url)
        crm_match = re.search(r"flat_id:\s*['\"]([^'\"]+)['\"]", html)
        if crm_match:
            external_id = crm_match.group(1)

        flat_el = tree.css_first(".m-FlatCard__info-flat")
        flat_label = flat_el.text(separator=" ", strip=True) if flat_el else external_id
        details_el = tree.css_first(".m-FlatCard__info-details")
        details = details_el.text(separator=" ", strip=True) if details_el else ""
        price_el = tree.css_first(".m-FlatCard__info-price .m-FlatCard__info-priceRight span")
        price = parse_money(price_el.text(strip=True) if price_el else None)
        investment_match = re.search(r"investment:\s*['\"]([^'\"]+)['\"]", html)
        investment = investment_match.group(1) if investment_match else "Euro Styl"

        images: list[str] = []
        for img in tree.css("img[data-src], img[src]"):
            src = img.attributes.get("data-src") or img.attributes.get("src") or ""
            if src and not src.endswith(".svg"):
                images.append(absolute_url(src, _BASE_URL))

        area = parse_area(details)
        rooms = parse_rooms(details)
        floor = parse_floor(details)
        if price is None and area is None and rooms is None:
            return None

        return RawListing(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=f"{investment} {flat_label}",
            price=price,
            area_m2=area,
            rooms=rooms,
            floor=floor,
            city="Gdańsk",
            market="primary",
            images=unique_listing_images(images),
            attributes={
                "investment": investment,
                "url_id": query_id_match.group(1) if query_id_match else None,
            },
        )

    def _parse_apartments_api(self, body: str, url: str) -> list[RawListing]:
        """Parse the Euro Styl search API response into individual apartment listings."""
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

        data = (
            payload
            if isinstance(payload, list)
            else (payload.get("data") or payload.get("results") or payload.get("items") or [])
        )
        if not isinstance(data, list):
            return []

        ext_id = slug(url)
        city = city_from_url(url, _CITY_MAP)
        listings: list[RawListing] = []

        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("ID")
            if item_id is None:
                continue
            item_id = str(item_id)

            title = str(item.get("name") or item.get("title") or f"Mieszkanie {item_id}")

            price_obj = item.get("price") or {}
            price = parse_money(
                str(price_obj.get("value") or price_obj.get("gross") or price_obj.get("net") or "")
            )

            area_m2 = parse_area(str(item.get("area") or item.get("squareMeters") or ""))
            rooms = parse_rooms(str(item.get("rooms") or item.get("pokoje") or ""))
            floor_val = None
            fl = item.get("floor") or item.get("pietro")
            if fl is not None:
                try:
                    floor_val = int(fl)
                except TypeError, ValueError:
                    pass

            images: list[str] = []
            for img_key in ("images", "photos", "gallery"):
                raw_images = item.get(img_key, [])
                if isinstance(raw_images, list):
                    for img in raw_images:
                        if isinstance(img, str):
                            images.append(absolute_url(img, _BASE_URL))
                        elif isinstance(img, dict):
                            for attr in ("url", "src", "full", "thumb"):
                                val = img.get(attr) or ""
                                if val:
                                    images.append(absolute_url(val, _BASE_URL))
                                    break

            status = item.get("status") or item.get("availability") or ""

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
                    market="primary",
                    images=unique_listing_images(images),
                    description=item.get("description") or item.get("opis") or None,
                    attributes={
                        "investment": ext_id,
                        "flat_id": item_id,
                        "status": status,
                    },
                    raw=item,
                )
            )

        return listings

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        if "/iapi/search" in url:
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
            market="primary",
        )


register(EuroStylScraper())
