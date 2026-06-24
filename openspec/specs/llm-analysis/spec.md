## Purpose

Describe the implemented LLM-backed enrichment, deduplication, and hybrid-search fallback behavior.

## Requirements

### Requirement: Listing Enrichment Service
The system SHALL provide a backend enrichment service that, when invoked with an LLM client, generates listing summaries, extracts feature dictionaries, and stores embeddings for normalized listings.

#### Scenario: Up-to-date listings are skipped
- **WHEN** a listing already has an `LLMAnalysis` for its current `raw_hash` and also has a stored embedding
- **THEN** the enrichment service does not reprocess that listing

### Requirement: Embedding Input Construction
The enrichment service SHALL build listing embeddings from the available title, location context, generated summary, and raw description.

#### Scenario: Embedding text prefers both curated and raw content
- **WHEN** the service generates an embedding for a listing
- **THEN** it uses a combined text built from title, district or city, summary, and raw description when those fields are present

### Requirement: Duplicate Group Detection Service
The system SHALL provide a backend deduplication service that, when invoked with an LLM client, groups listings that represent the same physical property and persists only duplicate groups with at least two valid members.

#### Scenario: Invalid or singleton groups are ignored
- **WHEN** the deduplication client returns malformed groups, unknown listing IDs, or groups smaller than two listings
- **THEN** those groups are not persisted

### Requirement: Stored Analysis Exposure
The system SHALL expose stored LLM summaries, feature dictionaries, and duplicate listing IDs in listing detail responses when that data exists, while returning empty or null values when it does not.

#### Scenario: Listing detail returns latest available analysis
- **WHEN** a client requests `GET /listings/{id}` for a listing that already has LLM analysis and dedup membership
- **THEN** the response includes the latest stored summary, features, and peer duplicate listing IDs

### Requirement: Hybrid Search Degradation
The system SHALL use semantic retrieval and reranking only when both a natural-language query and an LLM client are available, and SHALL fall back to filtered SQL search when embedding or reranking cannot be completed.

#### Scenario: Natural-language search falls back safely
- **WHEN** a client supplies `q` but no LLM client is configured, no embedded candidates exist, or semantic processing fails
- **THEN** the API returns filtered listing results instead of failing the request

### Requirement: No Automatic Enrichment Trigger in Scrape Flow
The current implementation SHALL keep enrichment and deduplication as callable backend services rather than automatically invoking them from manual scrape, scheduler, or public API routes.

#### Scenario: Scrape completes without generating new analyses
- **WHEN** ingestion runs through `POST /scrape` or through the scheduler
- **THEN** listings are synchronized without automatically creating fresh LLM analyses or dedup groups during that run
