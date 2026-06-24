## Purpose

Define the implemented scheduler and real-time event behavior for scraping operations.

## Requirements

### Requirement: In-Process Event Bus
The system SHALL publish scrape progress and scrape-log events through an in-process event bus that supports multiple subscribers.

#### Scenario: Manual scrape publishes progress events
- **WHEN** a manual scrape run reports source progress or log messages
- **THEN** the event bus publishes `scrape` and `scrape_log` payloads for active subscribers

### Requirement: SSE Event Stream Endpoint
The system SHALL expose `GET /events` as a server-sent events stream over the event bus.

#### Scenario: Connected client receives serialized events
- **WHEN** a client connects to `GET /events`
- **THEN** each published event is streamed as an SSE frame with its `type` as the event name and the full JSON payload as the data body

### Requirement: Optional Scheduler Startup
The system SHALL create the scrape scheduler during backend startup and only start scheduled execution when scheduler support is enabled by configuration.

#### Scenario: Startup respects configured scheduler mode
- **WHEN** the application starts with scheduler support enabled
- **THEN** it starts the scheduler using either the configured global cron expression or the configured default interval, plus any persisted per-source cron overrides

#### Scenario: Startup does not fully hydrate scheduler state from persisted settings
- **WHEN** the application boots without a runtime settings update
- **THEN** scheduler enablement and the base schedule come from environment-backed settings, while persisted per-source cron overrides can still be applied at startup

### Requirement: Scheduled Scrape Selection
The scheduler SHALL prefer saved searches that include a valid `city` filter and SHALL fall back to configured default cities when no such saved searches are available.

#### Scenario: Saved searches drive scheduled scrape criteria
- **WHEN** saved searches exist and at least one contains a valid city inside its `filters`
- **THEN** the scheduler runs scraping for those saved-search criteria instead of the default-city fallback

#### Scenario: Default-city fallback avoids gone-marking
- **WHEN** the scheduler falls back to default cities because no usable saved searches were found
- **THEN** it runs those scrapes with `mark_missing_gone` disabled

### Requirement: Persisted Scheduler Controls
The scheduler SHALL honor persisted `enabled_source_ids`, `source_max_pages`, and `source_crons` settings when building scheduled scrape runs.

#### Scenario: Persisted source settings shape scheduled runs
- **WHEN** source enablement, page limits, or per-source cron settings are saved in app settings
- **THEN** scheduled scraping uses those persisted values when selecting sources and page budgets

### Requirement: Runtime Scheduler Reconfiguration
The settings update flow SHALL reconfigure the in-memory scheduler immediately when the backend is already running.

#### Scenario: Settings update changes live scheduler behavior
- **WHEN** a client updates scheduler enablement, interval, cron, or per-source cron settings through `PUT /settings`
- **THEN** the running scheduler is started, restarted, or paused according to the updated settings without requiring an application restart
