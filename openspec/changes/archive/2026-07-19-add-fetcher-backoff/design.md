## Context

Two fetch paths exist today:

1. **Browser path** — `BrowserFetcher.fetch` (`scrapers/browser.py`) drives Playwright, enforces `scraper_min_delay_seconds` throttle (`_throttle`), and retries **only** on HTTP `429` with linear growth honoring `Retry-After`. Any other block (`403` from CloudFront, `401`, `5xx`, or a `is_blocked()` page) raises `ScraperBlocked` immediately.
2. **Plain-HTTP path** — `helpers.fetch_text` / `helpers.fetch_json` (`scrapers/helpers.py`) call `urlopen` once. On any non-2xx or transport error they raise; there is no retry at all. Used by `adresowo`, `morizon`, `nieruchomosci-online`, and the developer scrapers.

Analysis of `docker compose logs` (last 12h) showed no `403`/`blocked`/`429` errors in the single captured run, but the code paths above prove transient blocks are fatal: a CloudFront `403` on otodom aborts the whole otodom run with no recovery, and every other scraper has no resilience to transient HTTP failures.

## Goals / Non-Goals

**Goals:**
- Recover from transient block/error responses via bounded retry with exponential backoff.
- Honor `Retry-After` when provided (already done for `429`; extend to all retryable statuses).
- Share one backoff policy across both fetch paths.
- Keep the existing `ScrapeRun` classification: exhausted retries → `ScraperBlocked` → `blocked` status, isolating the source from others.

**Non-Goals:**
- No captcha-solving or IP rotation; we only retry, not defeat anti-bot measures.
- No change to the geocoder (already throttled/cached) or to DB/schema/API.
- No change to the runner's empty-page retry (`runner.py:78-82`) — that stays as-is.

## Decisions

1. **Retryable status set** — retry on `429`, `403`, `401`, and `5xx`. Rationale: CloudFront returns `403` for blocked otodom requests; `5xx`/`401` are transient on upstream sites. `4xx` client errors other than `401`/`403` (e.g. `404`) are NOT retried (permanent).

   *Alternative considered:* retry only `403`/`429`. Rejected — too narrow; the plain-HTTP scrapers hit varied transient `5xx`.

2. **Backoff formula** — `delay = min(scraper_backoff_max_seconds, scraper_backoff_base_seconds * 2**attempt)`, overridden by `Retry-After` when present. `attempt` starts at `0`, so first retry waits `base`. Linear (current `429` behavior) is replaced by exponential to spread load. *Alternative:* keep linear. Rejected — exponential is standard for rate-limit recovery and already hinted by the `_RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)` growth.

3. **Attempt cap** — `scraper_max_retries` total attempts (default `4`, i.e. 1 initial + 3 retries). On exhaustion, raise `ScraperBlocked` (browser) / a raised `URLError`/HTTP error (plain path after logging). Config-driven so it can be tuned per deployment.

4. **Single shared helper** — extract `_backoff_delay(attempt, retry_after, settings)` in `browser.py` and a small `_http_retry` wrapper in `helpers.py` so both paths share the same formula and constants. Constants in `browser.py` (`_RATE_LIMIT_*`) are folded into the new settings.

5. **`is_blocked()` pages count as retryable** — when `page.goto` succeeds with a `2xx` but the content is a block page, treat it like a failed attempt (backoff + retry) instead of failing immediately, so a transient interstitial can self-heal.

## Risks / Trade-offs

- [Risk] Longer worst-case scrape time when a source is genuinely blocked (base × growth × retries). → Mitigation: capped attempts and `blocked` classification isolate it; throttle unchanged.
- [Risk] Retrying `403` that is permanent wastes time. → Mitigation: small default retry count; this matches current `429` retry behavior.
- [Risk] Plain-HTTP `urlopen` has no async; backoff uses `time.sleep`. → Mitigation: calls are already synchronous in `helpers`; fine for current scrapers. No new event-loop coupling.

## Migration Plan

- Add settings to `config.py` with safe defaults; no migration needed (settings only).
- Existing tests in `test_browser.py` assert `429` retry behavior — update to new exponential expectations and add `403`/`is_blocked` cases.
- Rollback: settings revert to effective no-op (set `scraper_max_retries=1`); code change is local to two modules.

## Open Questions

- None blocking. Default retry count (`4`) and base (`1.0s`) can be tuned after observing production logs.
