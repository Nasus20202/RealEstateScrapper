## MODIFIED Requirements

### Requirement: Browser Fetch Throttling and Block Detection
The scraper browser fetcher SHALL enforce a minimum delay between requests, use the configured navigation wait strategy and timeout, retry transient block/error responses and transient navigation failures with exponential backoff, and raise a block condition when anti-bot pages are detected or retries are exhausted.

#### Scenario: Anti-bot responses surface as blocked scrapes
- **WHEN** fetched page content matches configured anti-bot markers without expected listing content markers
- **THEN** the browser fetcher retries with exponential backoff and, if the block persists past `scraper_max_retries`, raises a scraper-blocked condition instead of returning the page as a normal scrape result

#### Scenario: Rate-limited responses are retried with backoff
- **WHEN** the response status is a retryable block status (`403`, `401`, `429`, or `5xx`)
- **THEN** the browser fetcher waits an exponential backoff delay (honoring `Retry-After` when present) and retries before succeeding or raising as blocked

#### Scenario: Transient navigation failures are retried with backoff
- **WHEN** the page navigation fails with a transient error (a navigation timeout or a network error) rather than returning an HTTP response
- **THEN** the browser fetcher waits an exponential backoff delay and retries, and if the failures persist past `scraper_max_retries`, raises a scraper-blocked condition instead of aborting the scrape run
