## Purpose

Defines the behavior contract for the Trojmiasto.pl classifieds scraper, which ingests secondary- and primary-market real-estate listings from `ogloszenia.trojmiasto.pl` into the shared listing catalog.

## ADDED Requirements

### Requirement: Source Registration
The system SHALL register the Trojmiasto.pl scraper under `source_id = "trojmiasto"` with the display name "Trojmiasto.pl" through the standard module import side-effect, making it available for scraping, settings, and scheduling workflows alongside existing sources.

#### Scenario: Source is discoverable
- **WHEN** the backend starts and imports the scraper package
- **THEN** the scraper is registered in the shared registry and enumerable by `source_id = "trojmiasto"`

### Requirement: Search URL Construction
The scraper SHALL build search-result URLs for the `nieruchomosci` "sprzedam" (for sale) sections, choosing the secondary-market category (`nieruchomosci-sprzedam-rynek-wtorny`) by default and the primary-market category (`nieruchomosci-sprzedam-rynek-pierwotny`) when `criteria.market` is `"primary"`. Pagination SHALL use the site's `strona` query parameter, with page 1 having no `strona` parameter.

#### Scenario: Default search targets the secondary market
- **WHEN** `build_search_url` is called with no `market` criterion
- **THEN** the returned URL is `https://ogloszenia.trojmiasto.pl/nieruchomosci-sprzedam-rynek-wtorny/` (with no pagination parameter for page 1)

#### Scenario: Pagination appends a page parameter
- **WHEN** `build_search_url` is called for page 2 or later
- **THEN** the returned URL appends `?strona=<page>` to the category URL

#### Scenario: Primary market criterion selects the developer category
- **WHEN** `build_search_url` is called with `criteria.market == "primary"`
- **THEN** the returned URL uses the `nieruchomosci-sprzedam-rynek-pierwotny` category

### Requirement: Search Results Parsing
The scraper SHALL parse a search-results page into a list of `RawListing` records, one per listing card (`article` with a `data-id` attribute), with `external_id` taken from the card's `data-id` and stable across re-scrapes. Each record SHALL include the offer URL and title, and SHALL populate price, area, rooms, floor, year of construction, location text, thumbnail image URLs, and the update timestamp when the card provides them.

#### Scenario: Listing card yields a complete record
- **WHEN** parsing a search page containing a listing card with price, area, rooms, floor, year, location, image, and update timestamp
- **THEN** the resulting `RawListing` has `source_id = "trojmiasto"`, a stable numeric `external_id`, an absolute `url`, a non-empty `title`, and populated price/area/rooms/floor/year/location/images fields

#### Scenario: Cards without detail fields degrade gracefully
- **WHEN** a listing card omits optional fields such as floor or year of construction
- **THEN** the missing fields are `None` and the listing is still returned

#### Scenario: Empty or non-listing pages end pagination
- **WHEN** a fetched page contains no listing cards
- **THEN** `parse_search` returns an empty list so the runner stops pagination

#### Scenario: Location text is decomposed best-effort
- **WHEN** a listing card's location text contains a city (and optionally a district and/or street)
- **THEN** `city`, `district`, and `street` are populated where recognizable, leaving unknown components as `None`

### Requirement: Detail Page Parsing
The scraper SHALL parse a listing detail page into a `RawListing` that enriches the search result with a full description, address, price, area, rooms, floor, year of construction, and gallery image URLs when present.

#### Scenario: Detail page provides description and gallery
- **WHEN** parsing a detail page that contains a description block and gallery images
- **THEN** the returned `RawListing` includes the description and a de-duplicated list of absolute gallery image URLs

#### Scenario: Detail result merges with search context
- **WHEN** the runner enriches a search result with its detail-page result
- **THEN** search-level fields that the detail page does not provide are preserved from the search result

### Requirement: Market Determination
The scraper SHALL derive each listing's `market` from the section being scraped rather than per-listing heuristics: `"secondary"` for the `rynek-wtorny` category and `"primary"` for the `rynek-pierwotny` category.

#### Scenario: Secondary-market category marks listings secondary
- **WHEN** listings are parsed from a `rynek-wtorny` search page
- **THEN** every returned `RawListing` has `market = "secondary"`

#### Scenario: Primary-market category marks listings primary
- **WHEN** listings are parsed from a `rynek-pierwotny` search page
- **THEN** every returned `RawListing` has `market = "primary"`

### Requirement: Field Contract Documentation
The system SHALL document the per-field availability of the Trojmiasto.pl scraper in `docs/scrapers-field-contract.md`, consistent with the documentation maintained for other sources.

#### Scenario: Contract lists search-level availability
- **WHEN** a developer reads the field contract
- **THEN** it states which `RawListing` fields are reliably populated at search-results level for the `trojmiasto` source, including the semantics of the timestamp field
