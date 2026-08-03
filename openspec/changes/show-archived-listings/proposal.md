## Why

Listings that disappear from their source are marked `gone` during scraping and become invisible everywhere in the UI. Users cannot revisit offers that were recently removed, compare them, or spot listings that vanished — all views filter to `status = 'active'` and there is no way to see archived (`gone`) listings at all.

## What Changes

- Add an opt-in filter to include archived (status `gone`) listings, defaulting to the current active-only behavior so existing queries and URLs are unaffected.
- Support the archived option consistently across the listing views: list page, map page (points and hexes), and stats page.
- Expose the option through the public API query surface (`/listings`, `/listings/map/points`, `/listings/map/hexes`, `/stats`) via a single `status` (or equivalent) parameter.
- Mark archived listings visually in the frontend so they are distinguishable from active offers.
- No data-model changes: `gone` is an existing enum value and no migration is required.

## Capabilities

### New Capabilities
- `archived-listings-visibility`: ability to opt into viewing listings with status `gone` across all listing views and APIs

### Modified Capabilities
- `listings-api`: listing search, map, and stats endpoints accept a status filter that can include archived (`gone`) listings
- `web-application`: listings, map, and stats views expose a control to show archived listings and render them distinctly

## Impact

- Backend:
  - `backend/src/realestate/search/filters.py` — `ListingFilters` gains a status filter; `apply_filters` no longer hardcodes active-only when a wider status is requested.
  - `backend/src/realestate/search/service.py` — the base active-status clause becomes conditional on the requested status.
  - `backend/src/realestate/api/routes_listings.py` — `/listings`, `/listings/map/points`, `/listings/map/hexes`, and `/stats` accept and forward the status parameter; the raw-SQL map hex path (`_map_filter_params`) and stats conditions (`_stats_conditions`) stop hardcoding `status = 'active'`.
  - `backend/src/realestate/api/schemas.py` — query/schema plumbing as needed (status is a simple string param, likely no new output fields beyond existing `status` on `ListingOut`).
  - Backend tests in `backend/tests/api/`, `backend/tests/repositories/`, `backend/tests/search/`.
- Frontend:
  - `frontend/src/api/types.ts` — `ListingsQuery`/`StatsQuery` gain a status field.
  - `frontend/src/api/client.ts` — `buildListingsQuery`/`getStats` serialize the status param.
  - `frontend/src/features/listings/ListingsPage.tsx` — status option in filter UI + URL state.
  - `frontend/src/features/listings/ListingsMapPage.tsx` — status option carried into map points/hex requests + URL state.
  - `frontend/src/features/stats/StatsPage.tsx` — status option in filter UI + URL state.
  - `frontend/src/features/listings/ListingCard.tsx` — visual indicator for archived listings.
  - Frontend tests for the three pages and the card.
- No database migration, no new dependencies, no schema change.

Non-goals: not adding a dedicated archive "trash" or restore workflow; not changing how listings become `gone`; not applying the option to saved searches or favorites resolution.
