"""Address geocoding for map coordinates.

The scraped listing data has no coordinates, so we geocode the street/city
address into lat/lon at ingestion time and store it on listings.lat/lon (columns
already exist). Default provider is OpenStreetMap Nominatim — free, no API key —
but the base URL/user-agent are configurable (nothing hardcoded). Geocoding is
best-effort: failures return None and never break a scrape.
"""
from __future__ import annotations

import asyncio
import time
from typing import Protocol, runtime_checkable

import httpx

from realestate.config import get_settings


def build_address_query(
    *, street: str | None, district: str | None, city: str | None
) -> str | None:
    """Build a human-readable address query for geocoding, or None if too sparse.

    City is required (a bare district/street is ambiguous). Poland is appended to
    keep results in-country.
    """
    if not city:
        return None
    parts = [p for p in (street, district, city) if p]
    return ", ".join([*parts, "Polska"])


@runtime_checkable
class Geocoder(Protocol):
    async def geocode(self, query: str) -> tuple[float, float] | None: ...


class NominatimGeocoder:
    """Nominatim-backed geocoder with per-process caching and throttling.

    Nominatim's usage policy requires a valid User-Agent and at most ~1 req/s;
    both are honored here. Results are cached by query string for the lifetime of
    the instance so re-scrapes don't re-hit the service for known addresses.
    """

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        min_delay_seconds: float,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._min_delay = min_delay_seconds
        self._timeout = timeout_seconds
        self._client = client
        self._owns_client = client is None
        self._cache: dict[str, tuple[float, float] | None] = {}
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request = time.monotonic()

    async def geocode(self, query: str) -> tuple[float, float] | None:
        async with self._lock:
            if query in self._cache:
                return self._cache[query]
            client = self._client or httpx.AsyncClient(timeout=self._timeout)
            try:
                await self._throttle()
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "jsonv2", "limit": 1},
                    headers={"User-Agent": self._user_agent},
                )
                resp.raise_for_status()
                data = resp.json()
                result: tuple[float, float] | None = None
                if isinstance(data, list) and data:
                    first = data[0]
                    result = (float(first["lat"]), float(first["lon"]))
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                result = None
            finally:
                if self._owns_client:
                    await client.aclose()
            self._cache[query] = result
            return result


def get_geocoder() -> Geocoder | None:
    """Build the configured geocoder, or None when geocoding is disabled."""
    settings = get_settings()
    if not settings.geocoding_enabled:
        return None
    return NominatimGeocoder(
        base_url=settings.geocoding_base_url,
        user_agent=settings.geocoding_user_agent,
        min_delay_seconds=settings.geocoding_min_delay_seconds,
        timeout_seconds=settings.geocoding_timeout_seconds,
    )
