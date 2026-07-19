## MODIFIED Requirements

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
