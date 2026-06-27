from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def absolute_url(href: str, base_url: str = "") -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return base_url + href


def slug(url: str) -> str:
    path = url.rstrip("/").split("/")[-1]
    return path or url


def slugify_city(city: str) -> str:
    city = city.strip().lower().replace("ł", "l")
    folded = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "-", folded.strip())


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip(" ,")
    return cleaned or None


def looks_like_street_or_code(text: str | None) -> bool:
    value = clean_text(text)
    if not value:
        return False
    lowered = value.lower()
    if re.search(r"\d", lowered):
        return True
    return bool(
        re.match(
            r"^(?:ul\.|ulica|aleja|al\.|plac|pl\.|skwer|bulwar|rondo)\b",
            lowered,
        )
    )


def parse_money(text: str | None) -> Decimal | None:
    """Parse a Polish price string like '918 000 zł' or '500000' into Decimal."""
    if not text:
        return None
    text = text.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            return Decimal(text)
        except InvalidOperation, ValueError:
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


def parse_area(text: str | None) -> float | None:
    """Parse a Polish area string like '52,80 m²' into a float."""
    if not text:
        return None
    text = text.strip()
    if re.fullmatch(r"\d+(?:[,.]\d+)?", text):
        try:
            return float(text.replace(",", "."))
        except TypeError, ValueError:
            return None
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:m[²2]|m2)\b", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(\d+(?:[,.]\d+)?)\s*m\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except TypeError, ValueError:
        return None


def parse_rooms(text: str | None) -> int | None:
    """Extract rooms count from text like '2 pokoje'."""
    if not text:
        return None
    match = re.search(r"(\d+)\s*(?:pok|poko)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_floor(text: str | None) -> int | None:
    """Extract floor number from text like 'piętro 4' or 'parter'."""
    if not text:
        return None
    match = re.search(r"pi[eę]tro\s*(\d+)", text)
    if match:
        return int(match.group(1))
    if re.search(r"parter", text, re.IGNORECASE):
        return 0
    return None


def parse_total_floors(text: str | None) -> int | None:
    """Extract total floors from text like 'piętro 4/4'."""
    if not text:
        return None
    match = re.search(r"pi[eę]tro\s*\d+/(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"parter/(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def parse_int_text(text: str | None) -> int | None:
    """Extract integer from text by stripping non-digit characters."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text.strip())
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except TypeError, ValueError:
        return None


def parse_int_value(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def parse_float_value(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except TypeError, ValueError:
        return None


def image_url(node, base_url: str = "") -> str:
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        raw = node.attrs.get(attr) if hasattr(node, "attrs") else node.attributes.get(attr, "")
        value = raw or ""
        if value and not value.startswith("data:"):
            return absolute_url(value, base_url)
    srcset = (
        node.attrs.get("srcset") if hasattr(node, "attrs") else node.attributes.get("srcset", "")
    )
    if srcset:
        return absolute_url(srcset.split(",")[0].strip().split(" ")[0], base_url)
    style = node.attrs.get("style") if hasattr(node, "attrs") else node.attributes.get("style", "")
    if style:
        style_match = re.search(r"url\(['\"]?([^)'\"]+)", style)
        if style_match:
            return absolute_url(style_match.group(1), base_url)
    return ""


def city_from_text(text: str, city_map: dict[str, str]) -> str | None:
    for name in city_map.values():
        if name.lower() in text.lower():
            return name
    return None


def city_from_url(url: str, city_map: dict[str, str]) -> str | None:
    url_lower = url.lower()
    for key, name in city_map.items():
        if f"/{key}" in url_lower:
            return name
    return None


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    form_data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
):
    body = None
    request_headers = {
        "User-Agent": "Mozilla/5.0",
        **(headers or {}),
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
        request_headers["Accept"] = "application/json"
    elif form_data is not None:
        body = urlencode(form_data).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request_headers["Accept"] = "*/*"
    else:
        request_headers["Accept"] = "application/json"
    req = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(req, timeout=timeout) as response:  # noqa: S310 - public scraper sources
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0) -> str:
    request_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0",
        **(headers or {}),
    }
    req = Request(url, headers=request_headers, method="GET")
    with urlopen(req, timeout=timeout) as response:  # noqa: S310 - public scraper sources
        return response.read().decode("utf-8", errors="replace")


def add_query_params(url: str, params: dict[str, str]) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urlencode(params)}"
