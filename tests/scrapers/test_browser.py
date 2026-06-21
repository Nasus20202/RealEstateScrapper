import functools
import http.server
import threading

import pytest

from realestate.scrapers.browser import BrowserFetcher, is_blocked


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
        '<html><head><title>Oferta mieszkania – otodom.pl</title></head>'
        '<body><script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>'
        '<h1>oferta</h1>'
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
