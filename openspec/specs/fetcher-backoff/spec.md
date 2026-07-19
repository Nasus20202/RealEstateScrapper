# fetcher-backoff Specification

## Purpose
TBD - created by archiving change add-fetcher-backoff. Update Purpose after archive.
## Requirements
### Requirement: Fetcher Retry and Exponential Backoff
The scraper fetchers SHALL retry transient block/error responses using exponential backoff, honoring `Retry-After` when supplied, up to a configured maximum number of attempts.

#### Scenario: Retryable status triggers backoff before success
- **WHEN** a fetch returns a retryable status (`403`, `401`, `429`, or any `5xx`)
- **THEN** the fetcher waits an exponential backoff delay (capped by `scraper_backoff_max_seconds` and overridden by `Retry-After` if present) and retries, succeeding once a non-retryable response is returned

#### Scenario: Blocked page content triggers backoff
- **WHEN** `page.goto` returns a success status but the content matches anti-bot markers without listing content markers
- **THEN** the fetcher treats it as a failed attempt, applies backoff, and retries instead of raising immediately

#### Scenario: Exhausted retries surface as a block
- **WHEN** all retry attempts are consumed without a successful non-retryable response
- **THEN** the browser fetcher raises a scraper-blocked condition so the source is classified as `blocked`

#### Scenario: Retry budget is bounded by configuration
- **WHEN** `scraper_max_retries` is set
- **THEN** the total number of fetch attempts does not exceed that value

### Requirement: Plain-HTTP Fetch Resilience
The plain-HTTP fetch helpers (`fetch_text`, `fetch_json`) SHALL retry transient HTTP errors with the same backoff policy as the browser fetcher.

#### Scenario: Transient upstream error recovers
- **WHEN** a plain-HTTP fetch raises a transport or non-permanent HTTP error
- **THEN** the helper retries with exponential backoff up to `scraper_max_retries` before propagating the error

#### Scenario: Permanent client errors are not retried
- **WHEN** a plain-HTTP fetch returns a non-retryable status (e.g. `404`)
- **THEN** the helper does not retry and propagates the error immediately

