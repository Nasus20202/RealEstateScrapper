import functools
import http.server
import logging
import threading
from email.utils import formatdate
from types import SimpleNamespace

import pytest

from realestate.scrapers.base import ScraperBlocked
from realestate.scrapers.browser import BrowserFetcher, _retry_after_seconds, is_blocked


def test_is_blocked_detects_captcha_page():
    assert is_blocked("<html><title>Captcha</title>Please verify you are a human</html>")
    assert is_blocked("<html>access denied by datadome</html>")


def test_is_blocked_passes_normal_page():
    assert not is_blocked("<html><body><h1>Mieszkania Gdańsk</h1></body></html>")


def test_is_blocked_false_positive_legit_otodom_page():
    # Regression: legit otodom page — DataDome SDK script deep in body,
    # but real listing content (__NEXT_DATA__ / oferta) near the top.
    # Must NOT be flagged as blocked.
    top = (
        "<html><head><title>Oferta mieszkania – otodom.pl</title></head>"
        '<body><script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>'
        "<h1>oferta</h1>"
    )
    deep_sdk = " x" * 5000 + '<script src="https://cdn.datadome.com/tags.js"></script>'
    html = top + deep_sdk + "</body></html>"
    assert not is_blocked(html)


@pytest.fixture
def static_server(tmp_path):
    # serwuj prosty plik HTML
    content = "<html><body><h1>OK LISTING</h1></body></html>"
    (tmp_path / "page.html").write_text(content, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.mark.asyncio
async def test_fetch_returns_html_from_local_server(static_server):
    async with BrowserFetcher() as fetcher:
        html = await fetcher.fetch(f"{static_server}/page.html")
    assert "OK LISTING" in html


class _FakePage:
    def __init__(
        self, statuses: list[int], calls: list[str], retry_after_values: list[str | None]
    ) -> None:
        self._statuses = statuses
        self._calls = calls
        self._retry_after_values = retry_after_values

    async def goto(self, url: str, **_kwargs):
        self._calls.append(url)
        retry_after = self._retry_after_values.pop(0)

        async def header_value(name: str) -> str | None:
            return retry_after if name.lower() == "retry-after" else None

        return SimpleNamespace(status=self._statuses.pop(0), header_value=header_value)

    async def content(self) -> str:
        return "<html>OK LISTING</html>"

    async def close(self) -> None:
        return None


class _FakeContext:
    def __init__(
        self,
        statuses: list[int],
        calls: list[str],
        retry_after_values: list[str | None] | None = None,
    ) -> None:
        self._statuses = statuses
        self._calls = calls
        self._retry_after_values = retry_after_values or [None] * len(statuses)

    async def new_page(self) -> _FakePage:
        return _FakePage(self._statuses, self._calls, self._retry_after_values)


def test_retry_after_seconds_parses_delta_seconds():
    assert _retry_after_seconds("12") == 12.0


def test_retry_after_seconds_parses_http_date(monkeypatch):
    monkeypatch.setattr("realestate.scrapers.browser.time.time", lambda: 1000.0)
    assert _retry_after_seconds(formatdate(1015.0, usegmt=True)) == 15.0


@pytest.mark.asyncio
async def test_fetch_retries_429_before_returning(monkeypatch, caplog):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([429, 200], calls, ["7", None])  # noqa: SLF001

    async def no_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        return None

    monkeypatch.setattr("realestate.scrapers.browser.asyncio.sleep", no_sleep)

    with caplog.at_level(logging.WARNING, logger="realestate.scrapers.browser"):
        html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert calls == ["https://example.test/page", "https://example.test/page"]
    assert sleeps == [7.0]
    assert "Rate limited status=429" in caplog.text
    assert "delay_seconds=7.00" in caplog.text


@pytest.mark.asyncio
async def test_fetch_raises_blocked_after_repeated_429(monkeypatch, caplog):
    calls: list[str] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([429, 429, 429, 429], calls)  # noqa: SLF001

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("realestate.scrapers.browser.asyncio.sleep", no_sleep)

    with caplog.at_level(logging.WARNING, logger="realestate.scrapers.browser"):
        with pytest.raises(ScraperBlocked, match="429 Too Many Requests"):
            await fetcher.fetch("https://example.test/page")

    assert len(calls) == 4
    assert "Rate limit retry exhausted status=429" in caplog.text
