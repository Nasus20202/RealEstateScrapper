## MODIFIED Requirements

### Requirement: Browser Fetch Throttling and Block Detection
The scraper browser fetcher SHALL enforce a minimum delay between requests, use the configured navigation wait strategy and timeout, retry transient block/error responses with exponential backoff, and raise a block condition when anti-bot pages are detected after retries are exhausted.

#### Scenario: Anti-bot responses surface as blocked scrapes
- **WHEN** fetched page content matches configured anti-bot markers without expected listing content markers
- **THEN** the browser fetcher retries with exponential backoff and, if the block persists past `scraper_max_retries`, raises a scraper-blocked condition instead of returning the page as a normal scrape result

#### Scenario: Rate-limited responses are retried with backoff
- **WHEN** the response status is a retryable block status (`403`, `401`, `429`, or `5xx`)
- **THEN** the browser fetcher waits an exponential backoff delay (honoring `Retry-After` when present) and retries before succeeding or raising as blocked

## ADDED Requirements

### Requirement: Plain-HTTP Fetch Resilience
The plain-HTTP fetch helpers (`fetch_text`, `fetch_json`) SHALL retry transient HTTP errors with the same backoff policy as the browser fetcher, while rejecting non-retryable client errors without retry.

#### Scenario: Transient upstream error recovers
- **WHEN** a plain-HTTP fetch raises a transport or non-permanent HTTP error
- **THEN** the helper retries with exponential backoff up to `scraper_max_retries` before propagating the error

#### Scenario: Permanent client errors are not retried
- **WHEN** a plain-HTTP fetch returns a non-retryable status (e.g. `404`)
- **THEN** the helper does not retry and propagates the error immediately
