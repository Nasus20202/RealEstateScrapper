## Purpose

Define the implemented global saved-search, favorites, settings, and cleanup capabilities.

## Requirements

### Requirement: Saved Search Management
The system SHALL expose global saved-search CRUD through `GET /searches`, `POST /searches`, and `DELETE /searches/{id}` without per-user ownership.

#### Scenario: Saved search stores filters and optional natural-language query
- **WHEN** a client creates a saved search
- **THEN** the backend persists its name, arbitrary JSON filters, optional `nl_query`, and creation timestamp

### Requirement: Scheduler Consumption of Saved Searches
The scheduler SHALL only convert saved searches into scheduled scrape criteria when the saved-search `filters` object contains a valid `city` value.

#### Scenario: Natural-language query alone does not schedule a scrape
- **WHEN** a saved search has an `nl_query` but no valid city in `filters`
- **THEN** that saved search is ignored by the scheduled scrape runner

### Requirement: Favorites Management
The system SHALL expose global favorites through `GET /favorites`, `POST /favorites`, and `DELETE /favorites/{listing_id}`, and favorite creation SHALL be idempotent per listing.

#### Scenario: Adding the same listing twice does not create duplicates
- **WHEN** a client adds a favorite for a listing that is already favorited
- **THEN** the backend returns the existing favorite record instead of creating a second row

### Requirement: Settings Management and Secret Masking
The system SHALL expose application settings through `GET /settings` and `PUT /settings`, return only `llm_api_key_set` instead of the raw API key, and persist scheduler and scraper configuration in the `app_settings` table.

#### Scenario: Runtime settings update reconfigures the scheduler
- **WHEN** a client updates scheduler enablement, interval, cron, default cities, enabled sources, source page limits, or source crons
- **THEN** the backend persists those values and applies the resulting scheduler state to the in-memory scheduler if one is running

### Requirement: Settings Read Model
`GET /settings` SHALL return the LLM availability state, configured models, scheduler settings, default cities, registered source IDs, per-source page limits, and per-source cron overrides.

#### Scenario: Source catalog is derived from registered scrapers
- **WHEN** a client requests settings
- **THEN** the `sources` array reflects the currently registered scraper `source_id` values

#### Scenario: Some persisted scheduler inputs are write-only in the read model
- **WHEN** a client persists `enabled_source_ids` through `PUT /settings`
- **THEN** scheduled scraping can still use that persisted setting even though `GET /settings` does not currently return it

### Requirement: Cleanup Behavior
The system SHALL expose `POST /cleanup` to delete listings and their derived analysis data while leaving saved searches, scrape runs, and application settings intact.

#### Scenario: Cleanup removes listing-dependent data
- **WHEN** a client triggers cleanup
- **THEN** listings, price history, LLM analyses, dedup groups, and dedup members are deleted, and favorites tied to deleted listings are removed via foreign-key cascade
