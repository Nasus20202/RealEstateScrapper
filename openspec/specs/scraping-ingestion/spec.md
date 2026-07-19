## Purpose

Describe the implemented scraper, normalization, ingestion, and scrape-run behavior that keeps the listing catalog synchronized with upstream sources.
## Requirements
### Requirement: Scraper Plugin Registration
The system SHALL discover scraper plugins through module import side effects and expose them through a shared registry keyed by `source_id`.

#### Scenario: Registered sources are available to API and scheduler code
- **WHEN** the backend starts and the scraper package is imported
- **THEN** scraper implementations register themselves and can be enumerated for scraping, settings, and scheduling workflows

### Requirement: Search Execution Across Source Pages
The system SHALL run scraper searches page by page, stop on the first empty page, deduplicate results by `(source_id, external_id)`, and allow selected scrapers to enrich search results with detail-page data.

#### Scenario: Duplicate search results are suppressed
- **WHEN** the same upstream listing appears on multiple fetched pages or is expanded by detail parsing
- **THEN** the collected scrape result contains at most one item for that `(source_id, external_id)` pair

### Requirement: Browser Fetch Throttling and Block Detection
The scraper browser fetcher SHALL enforce a minimum delay between requests, use the configured navigation wait strategy and timeout, retry transient block/error responses with exponential backoff, and raise a block condition when anti-bot pages are detected after retries are exhausted.

#### Scenario: Anti-bot responses surface as blocked scrapes
- **WHEN** fetched page content matches configured anti-bot markers without expected listing content markers
- **THEN** the browser fetcher retries with exponential backoff and, if the block persists past `scraper_max_retries`, raises a scraper-blocked condition instead of returning the page as a normal scrape result

#### Scenario: Rate-limited responses are retried with backoff
- **WHEN** the response status is a retryable block status (`403`, `401`, `429`, or `5xx`)
- **THEN** the browser fetcher waits an exponential backoff delay (honoring `Retry-After` when present) and retries before succeeding or raising as blocked

### Requirement: Normalization and Incremental Sync
The system SHALL normalize raw scraper records into canonical listings, compute a `raw_hash` for change detection, best-effort geocode missing coordinates, and incrementally sync each source into the database. Geocoding failures are best-effort: the geocoder retries transient HTTP and transport errors with exponential backoff, and on exhaustion (or a permanent error) returns no coordinates for that listing instead of failing the scrape.

#### Scenario: Changed listing updates reset derived data
- **WHEN** an incoming listing matches an existing record but its `raw_hash` changes
- **THEN** the system updates mutable listing fields, clears the stored embedding, records a new price-history row if the price changed, and refreshes `last_seen`

#### Scenario: Geocoding failures do not abort ingestion
- **WHEN** the configured geocoder returns no result or encounters HTTP or parse errors for an address query
- **THEN** ingestion continues without coordinates for that listing instead of failing the scrape

#### Scenario: Geocoding retries transient errors
- **WHEN** the configured geocoder hits a transient error (e.g. `429`/`5xx`/transport) for an address query within the retry budget
- **THEN** it retries with exponential backoff (honoring `Retry-After`) before returning no result, and ingestion continues without coordinates only if retries are exhausted

#### Scenario: Geocoding uses throttled cached address lookup
- **WHEN** geocoding is enabled and multiple listings resolve the same address query during a process lifetime
- **THEN** the geocoder can reuse the cached result and still respect its minimum request delay for uncached lookups

### Requirement: Gone and Reactivated Listing Handling
The system SHALL reactivate listings that reappear in scrape results and mark missing listings as gone only for successful source syncs where `mark_missing_gone` is enabled.

#### Scenario: Single-city scrape marks missing listings gone
- **WHEN** a manual scrape is executed for exactly one city
- **THEN** listings from that scrape scope that are no longer returned can be marked `gone`

#### Scenario: Multi-city or fallback scheduled scrape avoids premature removals
- **WHEN** scraping is performed across multiple cities in one request or from the scheduler's default-city fallback path
- **THEN** the system does not mark missing listings gone for that run

### Requirement: Scrape Run Recording and Error Isolation
The system SHALL process each source in isolation, record a `ScrapeRun` for every source attempt, and classify outcomes as success, blocked, or failed without aborting unrelated sources.

#### Scenario: One blocked source does not stop other sources
- **WHEN** a scraper raises a block condition or another source fails unexpectedly
- **THEN** that source receives a `ScrapeRun` with the appropriate failure status while other sources can continue processing

### Requirement: Manual Scrape API
The system SHALL expose `POST /scrape`, `GET /scrape/runs`, and `GET /scrape/runs/{id}` for synchronous manual scraping and scrape-run inspection.

#### Scenario: Manual scrape merges persisted and request-scoped source page limits
- **WHEN** a client submits `POST /scrape` with optional `source_max_pages`
- **THEN** the backend merges those values with persisted per-source page settings before invoking ingestion

### Requirement: Plain-HTTP Fetch Resilience
The plain-HTTP fetch helpers (`fetch_text`, `fetch_json`) SHALL retry transient HTTP errors with the same backoff policy as the browser fetcher, while rejecting non-retryable client errors without retry.

#### Scenario: Transient upstream error recovers
- **WHEN** a plain-HTTP fetch raises a transport or non-permanent HTTP error
- **THEN** the helper retries with exponential backoff up to `scraper_max_retries` before propagating the error

#### Scenario: Permanent client errors are not retried
- **WHEN** a plain-HTTP fetch returns a non-retryable status (e.g. `404`)
- **THEN** the helper does not retry and propagates the error immediately

