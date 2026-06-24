## Purpose

Define the implemented platform baseline for the Real Estate Listing Aggregator, including runtime composition, persistence, and startup invariants.

## Requirements

### Requirement: Runtime Composition
The system SHALL run as a FastAPI backend, a standalone React frontend, and a shared PostgreSQL database, with API routes mounted at the application root and optionally exposed behind a reverse-proxy `/api` prefix.

#### Scenario: Root-level API routes
- **WHEN** the backend application is started directly
- **THEN** routes such as `/health`, `/listings`, `/scrape`, `/events`, `/searches`, `/favorites`, and `/settings` are served from the app root rather than from a versioned `/api/v1` namespace

### Requirement: PostgreSQL Feature Set
The system SHALL persist application data in PostgreSQL with both `pgvector` and PostGIS capabilities enabled for listing embeddings and geospatial map queries.

#### Scenario: Listing storage supports vector and map features
- **WHEN** listings are stored with embeddings and latitude/longitude coordinates
- **THEN** the database supports vector similarity over `listings.embedding` and geospatial queries over the PostGIS-backed `listings.geom` point

### Requirement: Canonical Persistent Data Model
The system SHALL persist normalized listings, price history, scrape runs, LLM analyses, duplicate groups, saved searches, favorites, app settings, and source metadata as first-class records.

#### Scenario: Listing-related state is preserved across backend features
- **WHEN** scraping, search, deduplication, user-data, and scheduler features interact with the database
- **THEN** they operate against shared persisted models for listings, price history, scrape runs, analyses, dedup groups, saved searches, favorites, app settings, and sources

### Requirement: Startup and Health Lifecycle
The system SHALL initialize the database engine and session factory at startup, optionally run migrations on startup, optionally start the scheduler, and expose database health through `GET /health`.

#### Scenario: Health check reports database readiness
- **WHEN** a client requests `GET /health`
- **THEN** the API returns `{"status":"ok","database":true}` when database connectivity and the `vector` extension check both pass, and a degraded response with HTTP 503 when they do not

### Requirement: MCP Mount
The system SHALL mount an MCP HTTP application alongside the FastAPI routes.

#### Scenario: MCP server is available from the backend app
- **WHEN** the backend application starts
- **THEN** it mounts the MCP application under `/mcp` in addition to the regular REST and SSE routes

### Requirement: Shared Embedding Dimension Configuration
The system SHALL use a single configured embedding dimension across migrations and runtime code so stored vectors remain compatible with the application.

#### Scenario: Migrations and runtime use the same dimension
- **WHEN** the embedding model or configured `EMBEDDING_DIM` changes
- **THEN** migrations and application runtime must use the same dimension for `listings.embedding`
