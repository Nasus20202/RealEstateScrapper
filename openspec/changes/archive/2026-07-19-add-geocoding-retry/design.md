## Context

`NominatimGeocoder.geocode` (`ingestion/geocode.py`) currently wraps a single `client.get` in `try/except httpx.HTTPError`, returning `None` on any error. Nominatim enforces ~1 req/s and returns `429` under load; the observed log showed exactly that. There is no recovery, so rate-limited listings lose coordinates for the process lifetime.

The scraper fetchers already implement exponential backoff with `Retry-After` support driven by `scraper_max_retries` / `scraper_backoff_base_seconds` / `scraper_backoff_max_seconds` in `config.py`, plus a shared `_retry_after_seconds` parser. We reuse that exact policy for geocoding to keep one backoff contract.

## Goals / Non-Goals

**Goals:**
- Recover geocoding coordinates from transient `429`/`5xx`/transport errors via bounded exponential backoff.
- Honor `Retry-After` when Nominatim supplies it.
- Keep permanent failures (other `4xx`, malformed JSON) non-retried and non-fatal.

**Non-Goals:**
- No new config keys — reuse the existing scraper backoff settings.
- No change to caching, throttling, or the geocoder interface.
- No change to how the scrape survives geocoding failure (still `None`, still non-aborting).

## Decisions

1. **Reuse scraper backoff settings** — avoids a new config surface; the user already tunes these. *Alternative:* dedicated `geocoding_max_retries`. Rejected for minimal config.
2. **Retry classification** — reuse `_is_retryable_status` (`401/403/429/5xx`) for `HTTPStatusError`, and retry all `TransportError`. Parse errors (`KeyError/ValueError/TypeError`) are permanent → no retry.
3. **Retry-After parsing** — `_retry_after_seconds` moved from `browser.py` into `helpers.py` and imported by both modules (single source of truth).
4. **Loop structure** — `for attempt in range(max_attempts)`: success or permanent failure `break`s; retryable failure `continue`s after sleeping. Result cached as `None` on exhaustion (unchanged).

## Risks / Trade-offs

- [Risk] Extra latency when Nominatim is genuinely rate-limiting. → Mitigation: capped `scraper_max_retries`; throttle unchanged.
- [Risk] Backoff sleeps slow tests. → Mitigation: tests monkeypatch `asyncio.sleep`.

## Migration Plan

- Settings-only reuse; no migration. Rollback by reverting `geocode.py` (settings remain harmless).
