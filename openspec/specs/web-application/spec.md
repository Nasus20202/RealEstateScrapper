## Purpose

Describe the implemented React web application behavior that sits on top of the backend APIs.

## Requirements

### Requirement: Application Routes and Navigation
The web application SHALL provide navigable pages for listings, map browsing, statistics, scraping operations, saved searches, favorites, and settings.

#### Scenario: Main application routes are available
- **WHEN** a user navigates through the SPA
- **THEN** the application serves `/`, `/mapa`, `/stats`, `/listings/:id`, `/scrape`, `/searches`, `/favorites`, and `/settings`

### Requirement: Listings Page Query-State Browsing
The listings page SHALL keep its filters and browsing state in URL query parameters and support multiple result layouts, sortable results, configurable page size, and in-page listing preview.

#### Scenario: Listing page state is shareable by URL
- **WHEN** a user changes search filters, natural-language query, sort order, page size, or view mode on the listings page
- **THEN** those choices are reflected in the URL and survive navigation or page refresh

#### Scenario: Card interactions separate preview from navigation
- **WHEN** a user single-clicks, double-clicks, or middle-clicks a listing card
- **THEN** the app respectively opens the side preview, opens the listing detail page, or opens the detail page in a new tab

### Requirement: Map and Statistics Views
The application SHALL provide a dedicated map page with viewport-driven point and hex loading and a statistics page with aggregated market metrics.

#### Scenario: Map requests follow the visible viewport
- **WHEN** a user pans or zooms the map
- **THEN** the frontend reloads map points or hexes for the visible bounds instead of fetching the full catalog

#### Scenario: Map page exposes a narrower filter surface than the listings page
- **WHEN** a user filters from the dedicated map page UI
- **THEN** the visible controls cover city, price range, room counts, market, and sources, while other carried query parameters can still affect requests through the URL

#### Scenario: Map point loading is capped for browser rendering
- **WHEN** the frontend requests map points
- **THEN** it requests at most 1000 point results for the visible area

#### Scenario: Stats page shows provider and market summaries
- **WHEN** a user opens the statistics page
- **THEN** the UI renders overview metrics and grouped breakdowns using the `/stats` API

### Requirement: Listing Detail Experience
The application SHALL show listing details with gallery navigation, optional map, price history, sanitized description content, raw attributes, LLM summary and features, duplicate links, and favorite toggling.

#### Scenario: Detail page adapts to available data
- **WHEN** a user opens a listing detail page
- **THEN** the page renders optional sections such as price history, map, duplicate links, and LLM analysis only when that data exists for the listing

### Requirement: Scrape Operations Page
The application SHALL provide a scraping page that can start manual scraping, show recent SSE progress and log messages, and display recent scrape runs.

#### Scenario: Manual scrape UI subscribes to live progress
- **WHEN** a user starts a scrape from the scrape page
- **THEN** the page shows incoming `scrape` and `scrape_log` events and refreshes the recent run list after the request completes

### Requirement: Saved Search Page Behavior
The application SHALL list saved searches, allow them to be applied back onto the listings page, and allow create and delete operations.

#### Scenario: Saved-search creation stores only name and NL query from the current UI
- **WHEN** a user creates a saved search from the current saved-search page
- **THEN** the frontend submits the search name, an optional natural-language query, and an empty `filters` object rather than persisting the current listings-page filter state

### Requirement: Favorites and Settings Pages
The application SHALL provide a favorites page that resolves favorite listing IDs into cards and a settings page for scheduler and provider configuration plus cleanup actions.

#### Scenario: Settings page is operational rather than per-user
- **WHEN** a user opens the settings page
- **THEN** the UI exposes global scheduler, default-city, provider, per-source page, per-source cron, and cleanup controls instead of personal preferences

#### Scenario: Cleanup requires a two-step confirmation in the UI
- **WHEN** a user initiates listing cleanup from the settings page
- **THEN** the first click arms the destructive action and the second click performs cleanup, with an explicit cancel path available before execution
