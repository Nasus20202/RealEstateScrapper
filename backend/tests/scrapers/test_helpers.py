from urllib.error import HTTPError, URLError

import pytest

import realestate.scrapers.helpers as helpers
from realestate.config import Settings
from realestate.scrapers.helpers import (
    _backoff_delay,
    _is_retryable_status,
    _retry_after_seconds,
    fetch_json,
    fetch_text,
)


class _FakeResp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def read(self) -> bytes:
        return self._data


class _FakeURLopener:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = outcomes
        self.calls: list[str] = []

    def __call__(self, req, timeout=None):
        self.calls.append(req.full_url)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResp(outcome)


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="postgresql://test",
        scraper_max_retries=4,
        scraper_backoff_base_seconds=1.0,
        scraper_backoff_max_seconds=30.0,
    )
    base.update(overrides)
    return Settings(**base)


# --- unit helpers ---------------------------------------------------------


def test_is_retryable_status():
    assert _is_retryable_status(401)
    assert _is_retryable_status(403)
    assert _is_retryable_status(429)
    assert _is_retryable_status(500)
    assert _is_retryable_status(503)
    assert not _is_retryable_status(404)
    assert not _is_retryable_status(400)


def test_retry_after_seconds_ignores_zero_and_negative():
    assert _retry_after_seconds("0") is None
    assert _retry_after_seconds("-5") is None
    assert _retry_after_seconds("") is None
    assert _retry_after_seconds(None) is None
    assert _retry_after_seconds("7") == 7.0
    assert _retry_after_seconds("1.5") == 1.5


def test_backoff_delay_never_zero():
    s = _settings(scraper_backoff_base_seconds=1.0)
    # Retry-After: 0 is treated as no hint -> falls back to base (positive).
    assert _backoff_delay(0, 0.0, s) == 1.0
    # A tiny Retry-After is floored to the base so retries are never instant.
    assert _backoff_delay(0, 0.5, s) == 1.0
    assert _backoff_delay(0, 7.0, s) == 7.0


def test_backoff_delay_grows_exponentially_and_caps():
    s = _settings()
    assert _backoff_delay(0, None, s) == 1.0
    assert _backoff_delay(1, None, s) == 2.0
    assert _backoff_delay(2, None, s) == 4.0
    # capping at max
    assert _backoff_delay(10, None, s) == 30.0
    # Retry-After overrides growth
    assert _backoff_delay(0, 7.0, s) == 7.0


# --- fetch_text / fetch_json resilience -----------------------------------


def test_fetch_text_retries_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(helpers, "get_settings", lambda: _settings())
    opener = _FakeURLopener([HTTPError("http://t", 503, "", None, None), b"<html>OK</html>"])
    monkeypatch.setattr(helpers, "urlopen", opener)
    sleeps: list[float] = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: sleeps.append(s))

    html = fetch_text("http://t")

    assert html == "<html>OK</html>"
    assert len(opener.calls) == 2
    assert sleeps == [1.0]


def test_fetch_text_retries_transport_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(helpers, "get_settings", lambda: _settings())
    opener = _FakeURLopener([URLError("boom"), b"ok"])
    monkeypatch.setattr(helpers, "urlopen", opener)
    sleeps: list[float] = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: sleeps.append(s))

    assert fetch_text("http://t") == "ok"
    assert len(opener.calls) == 2
    assert sleeps == [1.0]


def test_fetch_text_does_not_retry_404(monkeypatch):
    monkeypatch.setattr(helpers, "get_settings", lambda: _settings())
    opener = _FakeURLopener([HTTPError("http://t", 404, "", None, None), b"x"])
    monkeypatch.setattr(helpers, "urlopen", opener)

    with pytest.raises(HTTPError):
        fetch_text("http://t")

    assert len(opener.calls) == 1


def test_fetch_text_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(helpers, "get_settings", lambda: _settings(scraper_max_retries=3))
    opener = _FakeURLopener([HTTPError("http://t", 503, "", None, None) for _ in range(3)])
    monkeypatch.setattr(helpers, "urlopen", opener)

    with pytest.raises(HTTPError):
        fetch_text("http://t")

    assert len(opener.calls) == 3


def test_fetch_json_retries_401_then_succeeds(monkeypatch):
    monkeypatch.setattr(helpers, "get_settings", lambda: _settings())
    body = b'{"ok": true}'
    opener = _FakeURLopener([HTTPError("http://t", 401, "", None, None), body])
    monkeypatch.setattr(helpers, "urlopen", opener)
    sleeps: list[float] = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: sleeps.append(s))

    result = fetch_json("http://t")

    assert result == {"ok": True}
    assert len(opener.calls) == 2
    assert sleeps == [1.0]
