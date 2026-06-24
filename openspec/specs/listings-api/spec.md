## Purpose

Define the implemented listing, search, detail, statistics, and map APIs exposed by the backend.

## Requirements

### Requirement: MCP Listing Tools
The system SHALL expose MCP tools for listing search, listing detail retrieval, and high-level listing statistics.

#### Scenario: MCP clients can query listing data
- **WHEN** an MCP client uses the mounted backend MCP server
- **THEN** it can call tools for listing search, individual listing retrieval with detail sections, and high-level listing statistics

### Requirement: Filtered Listing Search Endpoint
The system SHALL expose `GET /listings` for active-listing search with structured filters, optional natural-language query input, sortable results, and limit/offset pagination.

#### Scenario: Structured search with filters and sorting
- **WHEN** a client requests `GET /listings` with any combination of `city`, `district`, `source_id`, price, area, rooms, `market`, `sort_by`, `sort_dir`, `limit`, and `offset`
- **THEN** the API returns matching active listings plus a total count

### Requirement: Hybrid Listing Ranking
The `GET /listings` endpoint SHALL pass the `q` parameter into hybrid search behavior that can combine filtered SQL results, vector retrieval over embedded listings, and optional LLM reranking.

#### Scenario: Natural-language query influences ranking
- **WHEN** a client requests `GET /listings?q=...`
- **THEN** the backend attempts semantic ranking for the filtered result set and includes optional `score` and `reason` values on returned listings when reranking data is available

### Requirement: Listing Detail Endpoint
The system SHALL expose `GET /listings/{id}` for full listing detail, including price history and any stored analysis data.

#### Scenario: Listing detail includes related detail sections
- **WHEN** a client requests an existing listing by ID
- **THEN** the response includes the listing fields, ordered price history, summary, features, and duplicate listing IDs

### Requirement: Statistics Endpoint
The system SHALL expose `GET /stats` for aggregated active-listing analytics, including overview metrics and grouped breakdowns by district, source, city, market, rooms, price bucket, and provider status.

#### Scenario: Provider-level stats include last run state
- **WHEN** a client requests `GET /stats`
- **THEN** provider rows include listing counts and the latest known scrape-run time and status for each source when available

### Requirement: Viewport-Based Map Points Endpoint
The system SHALL expose `GET /listings/map/points` for active listings with coordinates, filtered by the current viewport and other search filters.

#### Scenario: Point results are constrained for map rendering
- **WHEN** a client requests map points with or without viewport bounds
- **THEN** the API returns only active listings with coordinates and clamps the maximum point payload size for frontend rendering

### Requirement: PostGIS Hex Aggregation Endpoint
The system SHALL expose `GET /listings/map/hexes` for viewport-aware hexagonal aggregations of active geocoded listings using PostGIS.

#### Scenario: Hex query returns aggregate geometry and pricing
- **WHEN** a client requests map hexes for a viewport and filter set
- **THEN** the API returns hex cells with GeoJSON geometry, listing counts, and average price metrics

#### Scenario: Hex query failure degrades to empty results
- **WHEN** the PostGIS hex query fails because of a database or query-layer error
- **THEN** the API returns an empty hex list instead of failing the request
