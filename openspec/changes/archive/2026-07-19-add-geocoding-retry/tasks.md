## 1. Implementation

- [x] 1.1 Move `_retry_after_seconds` from `scrapers/browser.py` into `scrapers/helpers.py` and import it in both `browser.py` and `ingestion/geocode.py`.
- [x] 1.2 Add a bounded retry loop to `NominatimGeocoder.geocode` that retries `_is_retryable_status` `HTTPStatusError` and `TransportError` with `_backoff_delay` (honoring `Retry-After`); permanent failures and parse errors break without retry.

## 2. Tests

- [x] 2.1 In `tests/ingestion/test_geocode.py`: add tests for `429` recovery (retry then success), `Retry-After` honoring, exhausted retries → `None`, permanent `404` non-retry, and malformed-payload non-retry. Patch `asyncio.sleep` to keep tests fast.

## 3. Validation

- [x] 3.1 Run `uv run ruff check .` and `uv run ruff format .` in `backend/`.
- [x] 3.2 Run `uv run pytest` in `backend/` and confirm new tests pass.
- [x] 3.3 Run `openspec validate --specs` from repo root.
