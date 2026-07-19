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
    assert "Fetch retryable status=429" in caplog.text
    assert "delay_seconds=7.00" in caplog.text


@pytest.mark.asyncio
async def test_fetch_raises_blocked_after_repeated_429(monkeypatch, caplog):
    calls: list[str] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([429, 429, 429, 429], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings(scraper_max_retries=4)  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("realestate.scrapers.browser.asyncio.sleep", no_sleep)

    with caplog.at_level(logging.WARNING, logger="realestate.scrapers.browser"):
        with pytest.raises(ScraperBlocked, match="429 Too Many Requests"):
            await fetcher.fetch("https://example.test/page")

    assert len(calls) == 4
    assert "Fetch retry exhausted status=429" in caplog.text


class _FakeBlockPage:
    def __init__(self, status: int, calls: list[str], blocked: bool) -> None:
        self._status = status
        self._calls = calls
        self._blocked = blocked

    async def goto(self, url: str, **_kwargs):
        self._calls.append(url)
        return SimpleNamespace(status=self._status, header_value=self.header_value)

    async def header_value(self, _name: str):
        return None

    async def content(self) -> str:
        if self._blocked:
            return "<html><head><title>Access Denied</title></head><body>captcha</body></html>"
        return "<html>OK LISTING</html>"

    async def close(self) -> None:
        return None


class _FakeBlockContext:
    def __init__(self, statuses: list[int], calls: list[str]) -> None:
        self._statuses = statuses
        self._calls = calls
        self._pages = 0

    async def new_page(self) -> _FakeBlockPage:
        blocked = self._pages == 0
        self._pages += 1
        return _FakeBlockPage(self._statuses.pop(0), self._calls, blocked)


def _make_sleeper(sleeps: list[float]):
    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    return _sleep


def _fake_settings(**overrides):
    from types import SimpleNamespace

    base = dict(
        scraper_max_retries=4,
        scraper_backoff_base_seconds=1.0,
        scraper_backoff_max_seconds=30.0,
        scraper_min_delay_seconds=0.0,
        scraper_wait_until="domcontentloaded",
        scraper_nav_timeout_ms=30000,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_fetch_retries_403_before_returning(monkeypatch, caplog):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([403, 200], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    with caplog.at_level(logging.WARNING, logger="realestate.scrapers.browser"):
        html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert calls == ["https://example.test/page", "https://example.test/page"]
    assert sleeps == [1.0]
    assert "Fetch retryable status=403" in caplog.text


@pytest.mark.asyncio
async def test_fetch_retries_5xx_before_returning(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([503, 200], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert calls == ["https://example.test/page", "https://example.test/page"]
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_fetch_retries_blocked_page_before_returning(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    # 200 but anti-bot content, then a clean 200 page.
    fetcher._context = _FakeBlockContext([200, 200], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert len(calls) == 2
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_fetch_honors_retry_after_on_429(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([429, 200], calls, ["5", None])  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert sleeps == [5.0]


@pytest.mark.asyncio
async def test_fetch_does_not_retry_404(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    # content with "listing" marker so it is not flagged as blocked
    fetcher._context = _FakeContext([404, 200], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_fetch_raises_blocked_after_repeated_403(monkeypatch, caplog):
    calls: list[str] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeContext([403, 403, 403, 403], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("realestate.scrapers.browser.asyncio.sleep", no_sleep)

    with caplog.at_level(logging.WARNING, logger="realestate.scrapers.browser"):
        with pytest.raises(ScraperBlocked, match="Blocked"):
            await fetcher.fetch("https://example.test/page")

    assert len(calls) == 4
    assert "Fetch retry exhausted status=403" in caplog.text


class _FakeClosedHeaderPage:
    def __init__(self, statuses: list[int], calls: list[str]) -> None:
        self._statuses = statuses
        self._calls = calls

    async def goto(self, url: str, **_kwargs):
        self._calls.append(url)
        return SimpleNamespace(
            status=self._statuses.pop(0),
            header_value=self.header_value,
        )

    async def header_value(self, _name: str):
        # Simulate Playwright's TargetClosedError when headers are read late.
        raise RuntimeError("Target page, context or browser has been closed")

    async def content(self) -> str:
        return "<html>OK LISTING</html>"

    async def close(self) -> None:
        return None


class _FakeClosedHeaderContext:
    def __init__(self, statuses: list[int], calls: list[str]) -> None:
        self._statuses = statuses
        self._calls = calls

    async def new_page(self) -> _FakeClosedHeaderPage:
        return _FakeClosedHeaderPage(self._statuses, self._calls)


@pytest.mark.asyncio
async def test_fetch_tolerates_header_read_failure(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []
    fetcher = BrowserFetcher()
    fetcher._context = _FakeClosedHeaderContext([429, 200], calls)  # noqa: SLF001
    fetcher._settings = _fake_settings()  # noqa: SLF001
    monkeypatch.setattr("realestate.scrapers.browser.get_settings", _fake_settings)
    monkeypatch.setattr(
        "realestate.scrapers.browser.asyncio.sleep",
        _make_sleeper(sleeps),
    )

    html = await fetcher.fetch("https://example.test/page")

    assert "OK LISTING" in html
    assert len(calls) == 2
    # No Retry-After read -> exponential backoff (1.0s) instead of crashing.
    assert sleeps == [1.0]
