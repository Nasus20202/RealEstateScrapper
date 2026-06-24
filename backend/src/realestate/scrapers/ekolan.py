"""Ekolan.pl scraper — Tricity property developer, parses rendered DOM cards."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser

from realestate.scrapers.base import RawListing, SearchCriteria, register
from realestate.scrapers.helpers import fetch_text
from realestate.scrapers.images import unique_listing_images

_BASE_URL = "https://www.ekolan.pl"

_CITY_MAP: dict[str, str] = {
    "gdansk": "Gdańsk",
    "gdynia": "Gdynia",
    "sopot": "Sopot",
    "rumia": "Rumia",
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


def _money_range(text: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not text:
        return None, None
    matches = re.findall(
        r"(\d[\d\s\xa0]*(?:,\d+)?)\s*(?:-|–)?\s*(?:\d[\d\s\xa0]*(?:,\d+)?)?\s*(?:zł|PLN)",
        text,
        flags=re.IGNORECASE,
    )
    if len(matches) >= 2:
        return _money(matches[0] + " zł"), _money(matches[1] + " zł")
    if matches:
        val = _money(matches[0] + " zł")
        return val, val
    return None, None


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


class EkolanScraper:
    source_id = "ekolan"
    display_name = "Ekolan"

    def __init__(self) -> None:
        self._last_city: str | None = None

    def build_search_url(self, criteria: SearchCriteria, page: int = 1) -> str:
        self._last_city = criteria.city
        return f"{_BASE_URL}/oferta"

    def _parse_investment_card(self, card) -> dict | None:
        """Parse a single Ekolan investment card (.offer__item)."""
        link = card.css_first("a[href]")
        href = link.attributes.get("href", "") if link else ""
        name_el = card.css_first(".offer__item-title, h2, h3")
        text = name_el.text(strip=True) if name_el else ""
        if not text:
            return None

        url = _absolute_url(href.split("#")[0]) if href else ""
        ext_id = _investment_from_url(url) or re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if not ext_id:
            return None

        address_el = card.css_first(".offer__item-address")
        address_text = address_el.text(strip=True) if address_el else ""
        card_text = card.text(separator=" ", strip=True)

        city = _city_from_text(address_text) or _city_from_text(card_text)

        rooms_val = None
        area_val = None
        price_min, price_max = None, None

        for row in card.css(".offer__item-row"):
            label_el = row.css_first(".offer__item-label")
            value_el = row.css_first(".offer__item-value")
            if not label_el or not value_el:
                continue
            label = label_el.text(strip=True).lower()
            value = value_el.text(strip=True)
            if "pokoj" in label or "poko" in label:
                rooms_val = _rooms(value)
            elif "metra" in label or "area" in label:
                area_val = _area(value)
            elif "cen" in label or "price" in label:
                price_min, price_max = _money_range(value + " zł")

        return {
            "ext_id": ext_id,
            "url": url,
            "text": text,
            "city": city,
            "rooms": rooms_val,
            "area": area_val,
            "price_min": price_min,
            "price_max": price_max,
        }

    def parse_search(self, html: str) -> list[RawListing]:
        tree = HTMLParser(html)
        listings: list[RawListing] = []
        seen_ids: set[str] = set()

        for card in tree.css(".offer__item"):
            parsed = self._parse_investment_card(card)
            if not parsed:
                continue

            ext_id = parsed["ext_id"]
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            city = parsed["city"]
            if self._last_city:
                requested = _city_from_text(self._last_city) or self._last_city
                if city and requested.lower() not in city.lower():
                    continue

            attributes: dict = {"investment": ext_id}
            if parsed["price_min"] is not None:
                attributes["price_min"] = str(parsed["price_min"])
            if parsed["price_max"] is not None:
                attributes["price_max"] = str(parsed["price_max"])

            images: list[str] = []
            for img in card.css("img"):
                src = _image_url(img)
                if src and not src.endswith(".svg") and src not in images:
                    images.append(src)

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=ext_id,
                    url=parsed["url"] or f"{_BASE_URL}/oferta",
                    title=parsed["text"],
                    price=parsed["price_min"] or parsed["price_max"],
                    area_m2=parsed["area"],
                    rooms=parsed["rooms"],
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
        tree = HTMLParser(html)
        page_text = tree.body.text(strip=True) if tree.body else ""
        city = _city_from_text(page_text)
        apartments: list[RawListing] = []

        # Only attempt flat parsing if page contains apartment-like content
        if not re.search(r"(?:mieszkanie|apartament|flat|oferta\s+\d)", page_text[:5000]):
            return None

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

            price = _money(card_text)
            area_m2 = _area(card_text)
            if price is None and area_m2 is None:
                continue

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
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={"investment": ext_id, "flat_id": flat_id},
                )
            )

        return apartments if apartments else None

    def _parse_apartments_api(self, ext_id: str) -> list[RawListing] | None:
        """Fetch flats via subdomain getApartments endpoint."""
        # ext_id may be a bare slug (navigare) or a full hostname (navigare.ekolan.pl)
        slug = ext_id.replace(".ekolan.pl", "")
        subdomain_url = f"https://{slug}.ekolan.pl/getApartments.htm?submit=1"
        try:
            api_html = fetch_text(subdomain_url)
        except Exception:
            return None

        if not api_html or len(api_html) < 200:
            return None

        # Use regex to extract apartment rows (selectolax has issues with this HTML)
        # Table format: <tr[^>]*data-lokal='X'> (ALTRO style)
        table_rows = re.findall(
            r"<tr[^>]*clickable-row[^>]*>(.*?)</tr>",
            api_html,
            re.DOTALL,
        )
        if table_rows:
            return self._parse_ekolan_table(table_rows, slug, api_html)

        # Card format: split by <div class="b-flat-box" (NAVIGARE style)
        card_parts = re.split(r'<div class="b-flat-box\s*"[^>]*>', api_html)
        if len(card_parts) > 1:
            return self._parse_ekolan_cards(card_parts[1:], slug, api_html)

        return None

    def _parse_ekolan_table(
        self, rows: list[str], ext_id: str, api_html: str
    ) -> list[RawListing] | None:
        city = _city_from_text(api_html)
        listings: list[RawListing] = []
        for row_html in rows:
            lokal_m = re.search(r"data-lokal='([^']+)'", row_html)
            if not lokal_m:
                continue
            lokal = lokal_m.group(1)

            # Extract all <td> texts in order
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
            # Expected order: NR, Pokoje, metraż, piętro, cena_m2, cena
            rooms = _int(re.sub(r"<[^>]+>", "", tds[1]).strip()) if len(tds) > 1 else None

            area_raw = re.sub(r"<[^>]+>", " ", tds[2]).strip() if len(tds) > 2 else ""
            area_raw = re.sub(r"&nbsp;", " ", area_raw)
            area_m = re.search(r"(\d+(?:[,.]\d+)?)", area_raw)
            area_m2 = _float(area_m.group(1)) if area_m else None

            floor_val = _int(re.sub(r"<[^>]+>", "", tds[3]).strip()) if len(tds) > 3 else None

            # Price is the last column with "zł" values
            price = None
            if len(tds) > 5:
                price_raw = re.sub(r"<[^>]+>", " ", tds[5]).strip()
                price_raw = re.sub(r"&nbsp;", " ", price_raw)
                price_m = re.search(r"(\d[\d\s]*(?:[,.]\d+)?)\s*zł", price_raw)
                if price_m:
                    cleaned = price_m.group(1).replace(" ", "").replace(",", ".")
                    try:
                        val = Decimal(cleaned)
                        if val >= 1000:
                            price = val
                    except InvalidOperation, ValueError:
                        pass

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{lokal}",
                    url=f"https://{ext_id}.ekolan.pl/",
                    title=f"{ext_id} {lokal}",
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    market="primary",
                    attributes={
                        "investment": ext_id,
                        "flat_id": lokal,
                    },
                )
            )
        return listings if listings else None

    def _parse_ekolan_cards(
        self, cards: list[str], ext_id: str, api_html: str
    ) -> list[RawListing] | None:
        city = _city_from_text(api_html)
        listings: list[RawListing] = []
        for card_html in cards:
            eid_m = re.search(r"/apartamenty/apartament/\?eid=(\d+)", card_html)
            if not eid_m:
                continue
            eid = eid_m.group(1)

            nr_m = re.search(r"<h3>NR\s*(\d+)</h3>", card_html)
            flat_nr = nr_m.group(1) if nr_m else ""

            area_m = re.search(r"<span>metraż</span>\s*<p>(.*?)</p>", card_html, re.DOTALL)
            area_m2 = None
            if area_m:
                area_raw = re.sub(r"<[^>]+>", " ", area_m.group(1))
                area_raw = re.sub(r"&nbsp;", "", area_raw).strip()
                a_m = re.search(r"(\d+(?:[,.]\d+)?)", area_raw)
                area_m2 = _float(a_m.group(1)) if a_m else None

            rooms_m = re.search(r"<span>pokoje</span>\s*<p>\s*(\d+)\s", card_html)
            rooms = _int(rooms_m.group(1)) if rooms_m else None

            floor_m = re.search(r"<span>piętro</span>\s*<p>(.*?)</p>", card_html, re.DOTALL)
            floor_val = None
            if floor_m:
                floor_text = re.sub(r"<[^>]+>", "", floor_m.group(1)).strip().lower()
                if floor_text == "parter":
                    floor_val = 0
                else:
                    f_m = re.search(r"(\d+)", floor_text)
                    if f_m:
                        floor_val = _int(f_m.group(1))

            price_m = re.search(r"<span>cena brutto</span>\s*<p>(.*?)</p>", card_html, re.DOTALL)
            price = None
            if price_m:
                price_raw = re.sub(r"<[^>]+>", " ", price_m.group(1))
                price_raw = re.sub(r"&nbsp;", " ", price_raw)
                p_m = re.search(r"(\d[\d\s]*(?:[,.]\d+)?)\s*zł", price_raw)
                if p_m:
                    cleaned = p_m.group(1).replace(" ", "").replace(",", ".")
                    try:
                        val = Decimal(cleaned)
                        if val >= 1000:
                            price = val
                    except InvalidOperation, ValueError:
                        pass

            imgs = re.findall(r'<img[^>]*src="([^"]+)"', card_html)
            images = [url for url in imgs if not url.endswith(".svg")]

            listings.append(
                RawListing(
                    source_id=self.source_id,
                    external_id=f"{ext_id}-{eid}",
                    url=f"https://{ext_id}.ekolan.pl/",
                    title=f"{ext_id} {flat_nr}",
                    price=price,
                    area_m2=area_m2,
                    rooms=rooms,
                    floor=floor_val,
                    city=city,
                    market="primary",
                    images=unique_listing_images(images),
                    attributes={
                        "investment": ext_id,
                        "flat_id": eid,
                    },
                )
            )
        return listings if listings else None

    def parse_detail(self, html: str, url: str) -> RawListing | list[RawListing]:
        ext_id = _investment_from_url(url) or _slug(url)

        apartments = self._parse_apartments_api(ext_id)
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
            market="primary",
        )


register(EkolanScraper())
