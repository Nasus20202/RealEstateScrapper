from __future__ import annotations

import asyncio
import time

from playwright.async_api import async_playwright

from realestate.config import get_settings
from realestate.scrapers.base import ScraperBlocked

_BLOCK_MARKERS = ("captcha", "datadome", "access denied", "verify you are a human")


def is_blocked(html: str) -> bool:
    low = html.lower()
    # heurystyka: marker blokady + brak typowej treści ofert
    if any(m in low for m in _BLOCK_MARKERS) and "listing" not in low and "oferta" not in low:
        return True
    return False


class BrowserFetcher:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._pw = None
        self._browser = None
        self._context = None
        self._last_fetch = 0.0

    async def __aenter__(self) -> BrowserFetcher:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=self._settings.scraper_user_agent
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _throttle(self) -> None:
        delay = self._settings.scraper_min_delay_seconds
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_fetch = time.monotonic()

    async def fetch(self, url: str) -> str:
        await self._throttle()
        page = await self._context.new_page()
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._settings.scraper_nav_timeout_ms,
            )
            html = await page.content()
        finally:
            await page.close()
        if is_blocked(html):
            raise ScraperBlocked(url)
        return html
