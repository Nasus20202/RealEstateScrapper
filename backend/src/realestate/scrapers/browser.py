from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

from realestate.config import get_settings
from realestate.scrapers.base import ScraperBlocked

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright

_BLOCK_MARKERS = ("captcha", "datadome", "access denied", "verify you are a human")
_CONTENT_MARKERS = ("listing", "oferta", "__next_data__")


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
        page = await self._context.new_page()
        try:
            await page.goto(
                url,
                wait_until=self._settings.scraper_wait_until,
                timeout=self._settings.scraper_nav_timeout_ms,
            )
            if "hossa.gda.pl" in url:
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state("networkidle", timeout=5000)
            html = await page.content()
        finally:
            await page.close()
        if is_blocked(html):
            raise ScraperBlocked(url)
        return html
