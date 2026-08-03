## MODIFIED Requirements

### Requirement: Filtered Listing Search Endpoint

The system SHALL expose `GET /listings` for listing search with structured filters, optional natural-language query input, sortable results, and limit/offset pagination. The search SHALL include only active listings by default and SHALL accept an optional status filter to include archived (`gone`) listings.

#### Scenario: Structured search with filters and sorting

- **WHEN** a client requests `GET /listings` with any combination of `city`, `district`, `source_id`, price, area, rooms, `market`, `sort_by`, `sort_dir`, `limit`, and `offset`
- **THEN** the API returns matching active listings plus a total count

#### Scenario: Archived listings included via status filter

- **WHEN** a client requests `GET /listings` with a status filter that includes archived listings (e.g. `status=all`)
- **THEN** the API returns matching listings with status `active` and `gone` plus a total count, and each result still carries its `status` field

### Requirement: Statistics Endpoint

The system SHALL expose `GET /stats` for aggregated listing analytics, including overview metrics and grouped breakdowns by district, source, city, market, rooms, price bucket, and provider status. The statistics SHALL cover only active listings by default and SHALL accept an optional status filter to include archived (`gone`) listings.

#### Scenario: Provider-level stats include last run state

- **WHEN** a client requests `GET /stats`
- **THEN** provider rows include listing counts and the latest known scrape-run time and status for each source when available

#### Scenario: Stats include archived listings when requested

- **WHEN** a client requests `GET /stats` with a status filter that includes archived listings (e.g. `status=all`)
- **THEN** the overview metrics and grouped breakdowns are computed over listings with status `active` and `gone`

### Requirement: Viewport-Based Map Points Endpoint

The system SHALL expose `GET /listings/map/points` for listings with coordinates, filtered by the current viewport and other search filters. The endpoint SHALL return only active listings by default and SHALL accept an optional status filter to include archived (`gone`) listings.

#### Scenario: Point results are constrained for map rendering

- **WHEN** a client requests map points with or without viewport bounds
- **THEN** the API returns only active listings with coordinates and clamps the maximum point payload size for frontend rendering

#### Scenario: Map points include archived listings when requested

- **WHEN** a client requests map points with a status filter that includes archived listings (e.g. `status=all`)
- **THEN** the API returns points for listings with status `active` and `gone` that satisfy the viewport and other filters

### Requirement: PostGIS Hex Aggregation Endpoint

The system SHALL expose `GET /listings/map/hexes` for viewport-aware hexagonal aggregations of geocoded listings using PostGIS. The aggregation SHALL cover only active listings by default and SHALL accept an optional status filter to include archived (`gone`) listings.

#### Scenario: Hex query returns aggregate geometry and pricing

- **WHEN** a client requests map hexes for a viewport and filter set
- **THEN** the API returns hex cells with GeoJSON geometry, listing counts, and average price metrics computed over active listings

#### Scenario: Hex query includes archived listings when requested

- **WHEN** a client requests map hexes with a status filter that includes archived listings (e.g. `status=all`)
- **THEN** the hex cell counts and average price metrics are computed over listings with status `active` and `gone`

#### Scenario: Hex query failure degrades to empty results

- **WHEN** the PostGIS hex query fails because of a database or query-layer error
- **THEN** the API returns an empty hex list instead of failing the request
