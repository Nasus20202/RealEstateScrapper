## 1. Backend: status filter in the search path

- [x] 1.1 Add `status: Literal["active", "gone", "all"] = "active"` to `ListingFilters` in `backend/src/realestate/search/filters.py` and apply the matching `Listing.status` predicate in `apply_filters` (emit `== ACTIVE`, `== GONE`, or `in_([ACTIVE, GONE])`).
- [x] 1.2 In `backend/src/realestate/search/service.py`, drop the hardcoded `Listing.status == ListingStatus.ACTIVE` from the base queries in `search` and `search_hybrid` (the default in `ListingFilters` now provides active-only behavior).
- [x] 1.3 Update `backend/tests/search/test_search_filters.py` and `backend/tests/search/test_hybrid_search.py` to cover `status=gone` and `status=all` filter behavior (test first).

## 2. Backend: API routes accept and forward status

- [x] 2.1 Add `status: Literal["active", "gone", "all"] = Query("active")` to `/listings` in `backend/src/realestate/api/routes_listings.py` and forward it into `ListingFilters`.
- [x] 2.2 Add `status` to `_stats_conditions` and the `/stats` endpoint; emit the correct `Listing.status` predicate for each status value.
- [x] 2.3 Add `status` to `_listing_map_conditions` and the `/listings/map/points` endpoint.
- [x] 2.4 Add `status` to `_map_filter_params` (raw SQL) and the `/listings/map/hexes` endpoint; emit `"status = 'active'"`, `"status = 'gone'"`, or `"status IN ('active', 'gone')"`.
- [x] 2.5 Add API tests in `backend/tests/api/test_listings_api.py` asserting that `status=all` and `status=gone` return archived listings across `/listings`, `/listings/map/points`, `/listings/map/hexes`, and `/stats`, while the default still returns active-only (test first).

## 3. Backend: verify and commit

- [x] 3.1 Run `uv run pytest`, `uv run ruff check .`, and `uv run ruff format .` from `backend/`; fix any failures.
- [x] 3.2 Commit backend changes (test → implementation → commit).

## 4. Frontend: types and API client

- [x] 4.1 Add `status?: "active" | "gone" | "all"` to `ListingsQuery` and `StatsQuery` in `frontend/src/api/types.ts`.
- [x] 4.2 Serialize `status` in `buildListingsQuery` and `getStats` in `frontend/src/api/client.ts` (only when set, so default URLs are unchanged).
- [x] 4.3 Update `frontend/src/api/client.test.ts` to assert the `status` param round-trips (test first).

## 5. Frontend: archived option on listings view

- [x] 5.1 Add a "Pokaż zarchiwizowane" control to `ListingsPage` (`frontend/src/features/listings/ListingsPage.tsx`) wired into `FormState`, `buildQuery`, `formFromParams`, and `paramsFromState` via the `status` URL param.
- [x] 5.2 Update `frontend/src/features/listings/ListingsPage.test.tsx` to cover toggling the option, its URL persistence, and archived items being returned (test first).

## 6. Frontend: archived option on map view

- [x] 6.1 Add the archived-listings option to `ListingsMapPage` (`frontend/src/features/listings/ListingsMapPage.tsx`): extend `MapFilterState`/`filtersFromParams`/`queryFromParams`, ensure `paramsFromFilters` preserves the `status` key, and render the control.
- [x] 6.2 Update `frontend/src/features/listings/ListingsMapPage.test.tsx` to cover the toggle carrying `status` into map points/hex requests (test first).

## 7. Frontend: archived option on stats view

- [x] 7.1 Add the archived-listings option to `StatsPage` (`frontend/src/features/stats/StatsPage.tsx`): extend `FilterState`, `filtersFromParams`, `paramsFromFilters`, `queryFromFilters`, and render the control with an indication that archived listings are included.
- [x] 7.2 Update `frontend/src/features/stats/StatsPage.test.tsx` to cover the toggle sending `status` to `/stats` (test first).

## 8. Frontend: visual distinction for archived cards

- [x] 8.1 Add an archived badge/label to `ListingCard` (`frontend/src/features/listings/ListingCard.tsx`) shown when `listing.status === "gone"`.
- [x] 8.2 Update `frontend/src/features/listings/ListingCard.test.tsx` and add any needed styles in `frontend/src/styles.css` (test first).

## 9. Frontend: verify and commit

- [x] 9.1 Run `pnpm exec vitest run`, `pnpm lint`, `pnpm format`, and `pnpm build` from `frontend/`; fix any failures.
- [x] 9.2 Commit frontend changes (test → implementation → commit).

## 10. Final verification

- [x] 10.1 Run the full backend and frontend suites plus `openspec validate --changes` to confirm the change matches the delta specs.
