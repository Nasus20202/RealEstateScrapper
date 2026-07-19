from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

from realestate.config import get_settings
from realestate.scrapers.base import ScraperBlocked
from realestate.scrapers.helpers import (
    _backoff_delay,
    _is_retryable_status,
    _retry_after_seconds,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright

_BLOCK_MARKERS = ("captcha", "datadome", "access denied", "verify you are a human")
_CONTENT_MARKERS = ("listing", "oferta", "__next_data__")
logger = logging.getLogger(__name__)


def is_blocked(html: str) -> bool:
    # Scan only the title + first ~4000 chars so the DataDome SDK embedded deep
    # in legitimate otodom pages doesn't trigger a false positive.
    prefix_len = 4000
    prefix = html[:prefix_len].lower()
    full_low = html.lower()
    if any(m in prefix for m in _BLOCK_MARKERS) and not any(
        m in full_low for m in _CONTENT_MARKERS
    ):
        return True
    return False


class BrowserFetcher:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._last_fetch = 0.0

    async def __aenter__(self) -> BrowserFetcher:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=self._settings.scraper_user_agent
        )
        return self

    async def __aexit__(self, *exc) -> None:
        # Each step is guarded independently so that a failure in one step
        # never prevents the remaining resources from being released.
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass

    async def _throttle(self) -> None:
        delay = self._settings.scraper_min_delay_seconds
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_fetch = time.monotonic()

    async def fetch(self, url: str) -> str:
        assert self._context is not None, "BrowserFetcher must be used as an async context manager"
        await self._throttle()
        # domcontentloaded is the reliable default; JS-SPA pages needing full
        # render can set scraper_wait_until="networkidle" or use a per-scraper
        # wait-for-selector afterwards.
        max_attempts = max(1, self._settings.scraper_max_retries)
        for attempt in range(max_attempts):
            page = await self._context.new_page()
            retry_after: float | None = None
            try:
                response = await page.goto(
                    url,
                    wait_until=self._settings.scraper_wait_until,
                    timeout=self._settings.scraper_nav_timeout_ms,
                )
                status = response.status if response is not None else None
                # Read Retry-After while the response is still live; Playwright
                # invalidates the response channel after the page is used, so
                # guard against TargetClosedError and fall back to backoff only.
                if response is not None and status is not None and _is_retryable_status(status):
                    try:
                        raw = await response.header_value("retry-after")
                        retry_after = _retry_after_seconds(raw)
                    except Exception:  # noqa: BLE001 - header is an optional hint
                        retry_after = None
                html = await page.content()
            finally:
                await page.close()

            blocked = is_blocked(html)
            retryable = (status is not None and _is_retryable_status(status)) or blocked
            if not retryable:
                return html

            if attempt == max_attempts - 1:
                logger.warning(
                    "Fetch retry exhausted status=%s blocked=%s attempts=%s url=%s",
                    status,
                    blocked,
                    max_attempts,
                    url,
                )
                if status == 429:
                    raise ScraperBlocked(f"429 Too Many Requests: {url}")
                raise ScraperBlocked(f"Blocked (status={status}): {url}")

            delay = _backoff_delay(attempt, retry_after, self._settings)
            logger.warning(
                "Fetch retryable status=%s blocked=%s attempt=%s next_attempt=%s "
                "delay_seconds=%.2f retry_after=%s url=%s",
                status,
                blocked,
                attempt + 1,
                attempt + 2,
                delay,
                retry_after is not None,
                url,
            )
            await asyncio.sleep(delay)
        raise ScraperBlocked(url)
