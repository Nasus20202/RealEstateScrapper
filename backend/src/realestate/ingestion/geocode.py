"""Address geocoding for map coordinates.

The scraped listing data has no coordinates, so we geocode the street/city
address into lat/lon at ingestion time and store it on listings.lat/lon (columns
already exist). Default provider is OpenStreetMap Nominatim — free, no API key —
but the base URL/user-agent are configurable (nothing hardcoded). Geocoding is
best-effort: failures return None and never break a scrape.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Protocol, runtime_checkable

import httpx

from realestate.config import get_settings
from realestate.scrapers.helpers import (
    _backoff_delay,
    _is_retryable_status,
    _retry_after_seconds,
)

logger = logging.getLogger(__name__)


def build_address_query(
    *,
    street: str | None,
    district: str | None,
    city: str | None,
) -> str | None:
    """Build a human-readable address query for geocoding, or None if too sparse.

    City is required (a bare district/street is ambiguous). For exact street
    addresses keep the query broad-to-exact but omit district, because developer
    sites often put investment/marketing names there.
    """
    if not city:
        return None
    if street:
        parts = ["Polska", city, street]
    else:
        parts = ["Polska", city, district]
    return ", ".join(part for part in parts if part)


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
            delay = self._min_delay - elapsed
            logger.info("Geocoding throttled delay_seconds=%.2f", delay)
            await asyncio.sleep(delay)
        self._last_request = time.monotonic()

    async def geocode(self, query: str) -> tuple[float, float] | None:
        async with self._lock:
            if query in self._cache:
                logger.info("Geocoding cache hit query=%s", query)
                return self._cache[query]
            settings = get_settings()
            client = self._client or httpx.AsyncClient(timeout=self._timeout)
            result: tuple[float, float] | None = None
            max_attempts = max(1, settings.scraper_max_retries)
            try:
                for attempt in range(max_attempts):
                    logger.info("Geocoding request query=%s attempt=%s", query, attempt + 1)
                    await self._throttle()
                    try:
                        resp = await client.get(
                            f"{self._base_url}/search",
                            params={"q": query, "format": "jsonv2", "limit": 1},
                            headers={"User-Agent": self._user_agent},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        if isinstance(data, list) and data:
                            first = data[0]
                            result = (float(first["lat"]), float(first["lon"]))
                            logger.info("Geocoding matched query=%s", query)
                        else:
                            logger.info("Geocoding no result query=%s", query)
                        break
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        retry_after = _retry_after_seconds(exc.response.headers.get("retry-after"))
                        if attempt < max_attempts - 1 and _is_retryable_status(status):
                            delay = _backoff_delay(attempt, retry_after, settings)
                            logger.warning(
                                "Geocoding HTTP %s transient, retrying attempt=%s "
                                "delay_seconds=%.2f query=%s",
                                status,
                                attempt + 1,
                                delay,
                                query,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.warning(
                            "Geocoding HTTP error query=%s status=%s error=%s",
                            query,
                            status,
                            exc,
                        )
                        break
                    except httpx.TransportError as exc:
                        if attempt < max_attempts - 1:
                            delay = _backoff_delay(attempt, None, settings)
                            logger.warning(
                                "Geocoding transport error transient, retrying "
                                "attempt=%s delay_seconds=%.2f query=%s",
                                attempt + 1,
                                delay,
                                query,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.warning("Geocoding HTTP error query=%s error=%s", query, exc)
                        break
                    except (KeyError, ValueError, TypeError) as exc:
                        logger.warning("Geocoding parse error query=%s error=%s", query, exc)
                        break
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
