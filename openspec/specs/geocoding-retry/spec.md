# geocoding-retry Specification

## Purpose
TBD - created by archiving change add-geocoding-retry. Update Purpose after archive.
## Requirements
### Requirement: Geocoding Retry and Backoff
The geocoder SHALL retry transient geocoding failures (`429`, `401`, `403`, `5xx`, and transport errors) with exponential backoff honoring `Retry-After`, up to the configured maximum attempts, before returning no result.

#### Scenario: Transient rate-limit recovers
- **WHEN** Nominatim returns `429` (or another retryable status) and later succeeds within the retry budget
- **THEN** the geocoder returns the resolved coordinates without surfacing an error to the caller

#### Scenario: Retry honors Retry-After
- **WHEN** a retryable response includes a `Retry-After` header
- **THEN** the geocoder waits that duration before the next attempt instead of the default backoff step

#### Scenario: Exhausted retries yield no result
- **WHEN** all retry attempts are consumed without success
- **THEN** the geocoder returns `None` and the address is cached as failed for the process lifetime

#### Scenario: Permanent failures are not retried
- **WHEN** the geocoder receives a non-retryable `4xx` or a malformed payload
- **THEN** it does not retry and returns `None` immediately

