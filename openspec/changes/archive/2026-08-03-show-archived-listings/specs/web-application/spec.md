## MODIFIED Requirements

### Requirement: Listings Page Query-State Browsing

The listings page SHALL keep its filters and browsing state in URL query parameters and support multiple result layouts, sortable results, configurable page size, and in-page listing preview. The page SHALL include a control for including archived (`gone`) listings whose state is also kept in the URL.

#### Scenario: Listing page state is shareable by URL

- **WHEN** a user changes search filters, natural-language query, sort order, page size, archived-listings option, or view mode on the listings page
- **THEN** those choices are reflected in the URL and survive navigation or page refresh

#### Scenario: Card interactions separate preview from navigation

- **WHEN** a user single-clicks, double-clicks, or middle-clicks a listing card
- **THEN** the app respectively opens the side preview, opens the listing detail page, or opens the detail page in a new tab

#### Scenario: Archived listings are shown only when the option is enabled

- **WHEN** the archived-listings option on the listings page is off
- **THEN** the results contain only active listings

- **WHEN** the archived-listings option on the listings page is on
- **THEN** the results include archived listings, and archived listing cards are visually distinguishable from active ones

### Requirement: Map and Statistics Views

The application SHALL provide a dedicated map page with viewport-driven point and hex loading and a statistics page with aggregated market metrics. Both SHALL carry the archived-listings option so archived listings can be included in map and stats requests.

#### Scenario: Map requests follow the visible viewport

- **WHEN** a user pans or zooms the map
- **THEN** the frontend reloads map points or hexes for the visible bounds instead of fetching the full catalog

#### Scenario: Map page exposes a narrower filter surface than the listings page

- **WHEN** a user filters from the dedicated map page UI
- **THEN** the visible controls cover city, price range, room counts, market, sources, and the archived-listings option, while other carried query parameters can still affect requests through the URL

#### Scenario: Map point loading is capped for browser rendering

- **WHEN** the frontend requests map points
- **THEN** it requests at most 1000 point results for the visible area

#### Scenario: Stats page shows provider and market summaries

- **WHEN** a user opens the statistics page
- **THEN** the UI renders overview metrics and grouped breakdowns using the `/stats` API

#### Scenario: Stats page includes archived listings when enabled

- **WHEN** the archived-listings option on the statistics page is on
- **THEN** the overview metrics and grouped breakdowns are computed over listings with status `active` and `gone`, and the UI indicates that archived listings are included

#### Scenario: Map points and hexes include archived listings when enabled

- **WHEN** the archived-listings option on the map page is on
- **THEN** the map point and hex requests include archived listings, and the UI indicates that archived listings are included
