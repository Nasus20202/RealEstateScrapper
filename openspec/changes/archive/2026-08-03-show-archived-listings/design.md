## Context

Listings are hardcoded to `status = 'active'` in every read path:

- `SearchService.search` / `search_hybrid` build `select(Listing).where(Listing.status == ListingStatus.ACTIVE)` (`backend/src/realestate/search/service.py:52,90`), then pass through `apply_filters` (`backend/src/realestate/search/filters.py`).
- `/listings/map/points` builds conditions via `_listing_map_conditions` which starts with `Listing.status == ListingStatus.ACTIVE` (`backend/src/realestate/api/routes_listings.py:441`).
- `/listings/map/hexes` uses raw SQL from `_map_filter_params` which hardcodes `"status = 'active'"` (`routes_listings.py:367`).
- `/stats` builds `_stats_conditions` which starts with `Listing.status == ListingStatus.ACTIVE` (`routes_listings.py:60`).

`ListingStatus` already has `active` and `gone` enum values; `gone` is set by `mark_gone` during scrapes. No schema change is needed. The detail endpoint already returns any listing by id, so archived listings are reachable by URL today.

## Goals / Non-Goals

**Goals:**
- Add a status filter to the API surface (`/listings`, `/listings/map/points`, `/listings/map/hexes`, `/stats`) so archived (`gone`) listings can be included.
- Keep the current active-only behavior as the default so existing URLs and API consumers are unaffected.
- Expose an archived-listings option on the listings, map, and stats views, persisted in URL state and shareable.
- Visually distinguish archived listings from active ones on cards.

**Non-Goals:**
- No archive/unarchive workflow, trash, or restore.
- No change to how listings become `gone`.
- No change to saved-search apply or favorites resolution.
- No change to `/listings/filter-options` (remains active-only).

## Decisions

**D1: Use a `status` query parameter with values `active` | `gone` | `all`, default `active`.**
A single status param is more expressive than a boolean `include_archived` (allows "only archived" and maps directly to the existing `ListingStatus` enum). `active` is the default, preserving current behavior. Validation uses a `Literal` type so invalid values are rejected with 422 by FastAPI. `all` expands to `status IN ('active', 'gone')`.

**D2: Centralize status filtering in `ListingFilters.apply_filters`.**
Add `status: Literal["active", "gone", "all"] = "active"` to `ListingFilters` (`search/filters.py`). `apply_filters` applies the matching `Listing.status` predicate so the search path has a single source of truth. `SearchService` base queries become `select(Listing)` and drop the hardcoded `where(status == ACTIVE)` since the default now covers it.

**D3: Parameterize the route helper builders instead of hardcoding.**
- `_stats_conditions` and `_listing_map_conditions` take a `status` argument and emit `Listing.status == ACTIVE` / `== GONE` / `in_([ACTIVE, GONE])` accordingly. Each route (`/listings`, `/listings/map/points`, `/stats`) gains a `status: Literal[...] = Query("active")` parameter and forwards it.
- `_map_filter_params` (raw SQL for hexes) gains `status` and emits `"status = 'active'"`, `"status = 'gone'"`, or `"status IN ('active', 'gone')"` respectively; `/listings/map/hexes` gains the same `status` parameter.

**D4: Frontend carries `status` as a URL query param on all three views.**
`ListingsQuery` and `StatsQuery` gain `status?: "active" | "gone" | "all"`. `buildListingsQuery` and `getStats` serialize it. Each view (`ListingsPage`, `ListingsMapPage`, `StatsPage`) gets a "Pokaż zarchiwizowane" control backed by the `status` URL param (`status=all` when on, omitted when off), using the same params↔state plumbing already in place per page. Map page filters explicitly preserve the `status` key when rebuilding params (the existing `paramsFromFilters` deletes a fixed key list — `status` must be kept or re-added).

**D5: Visual distinction for archived cards.**
`ListingCard` renders a small archived badge/label when `listing.status === "gone"`, with styling distinct from active cards. No separate layout.

## Risks / Trade-offs

- **Raw SQL drift**: `_map_filter_params` is a hand-written clause list; forgetting to make `status` conditional there would silently keep hexes active-only. Covered by a test asserting `status=all` returns gone listings in hex counts.
- **Stats overview semantics**: `overview.total_count` counts all rows in the table regardless of filter, while `active_count` is filtered. With `status=all` these overlap; the UI already labels them separately ("Aktywne oferty" vs "łącznie w bazie") so no change is required, but the semantics of `active_count` when `status=all` become "all matching listings" — acceptable given the label indicates inclusion.
- **filter-options stays active-only**: archived listings in a city with no active listings won't appear in the city dropdown. Accepted trade-off; text search and NL query still work.
- **Performance**: including archived listings can grow result sets, but existing `limit`/`offset` and map caps bound payloads. Archived listings without coordinates (already the norm for `gone`) simply won't render on the map.
- **Backward compatibility**: new `status` param defaults to `active`; existing URLs, saved filters, and API clients keep working unchanged.
