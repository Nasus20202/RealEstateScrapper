from __future__ import annotations

import asyncio
import logging
import time
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

from realestate.config import get_settings
from realestate.scrapers.base import ScraperBlocked

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright

_BLOCK_MARKERS = ("captcha", "datadome", "access denied", "verify you are a human")
_CONTENT_MARKERS = ("listing", "oferta", "__next_data__")
_RATE_LIMIT_STATUS = 429
_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_BACKOFF_SECONDS = 10.0

logger = logging.getLogger(__name__)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except TypeError, ValueError:
            return None
        seconds = retry_at.timestamp() - time.time()
    return max(seconds, 0.0)


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
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            page = await self._context.new_page()
            try:
                response = await page.goto(
                    url,
                    wait_until=self._settings.scraper_wait_until,
                    timeout=self._settings.scraper_nav_timeout_ms,
                )
                if response is not None and response.status == _RATE_LIMIT_STATUS:
                    if attempt == _RATE_LIMIT_RETRIES:
                        logger.warning(
                            "Rate limit retry exhausted status=429 attempts=%s url=%s",
                            attempt + 1,
                            url,
                        )
                        raise ScraperBlocked(f"429 Too Many Requests: {url}")
                    retry_after = _retry_after_seconds(await response.header_value("retry-after"))
                    delay = retry_after or _RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Rate limited status=429 attempt=%s next_attempt=%s "
                        "delay_seconds=%.2f retry_after=%s url=%s",
                        attempt + 1,
                        attempt + 2,
                        delay,
                        retry_after is not None,
                        url,
                    )
                    await asyncio.sleep(delay)
                    continue
                html = await page.content()
            finally:
                await page.close()
            break
        if is_blocked(html):
            raise ScraperBlocked(url)
        return html
