# Superpowers Migration

`docs/superpowers/` is now a legacy planning archive.

The canonical capability specs live in `openspec/specs/` and were written to match the current implementation rather than the original June 2026 plan assumptions.

## OpenSpec Mapping

- `docs/superpowers/specs/2026-06-21-real-estate-aggregator-design.md`
  - Replaced by the implemented capability specs under `openspec/specs/`
- `plans/2026-06-21-01-foundation-and-storage.md`
  - Migrated into `openspec/specs/platform-foundation/spec.md`
- `plans/2026-06-21-02-scrapers.md`
  - Migrated into `openspec/specs/scraping-ingestion/spec.md`
- `plans/2026-06-21-03-ingestion.md`
  - Migrated into `openspec/specs/scraping-ingestion/spec.md`
- `plans/2026-06-21-04-llm-enrichment.md`
  - Migrated into `openspec/specs/llm-analysis/spec.md`
- `plans/2026-06-21-05-search-and-api.md`
  - Migrated into `openspec/specs/listings-api/spec.md`
- `plans/2026-06-21-06-scheduler-and-sse.md`
  - Migrated into `openspec/specs/automation-and-events/spec.md`
- `plans/2026-06-21-07-frontend.md`
  - Migrated into `openspec/specs/web-application/spec.md`
- Shared saved-search, favorites, settings, and cleanup behavior
  - Captured in `openspec/specs/user-workspace/spec.md`

## Scope Notes

- The old `docs/superpowers` plans included several aspirational items that are not implemented as of this migration, including a versioned `/api/v1` namespace, public enrichment endpoints, automatic enrichment during scraping, and the proposed E2E/CI slice.
- Those items were intentionally not copied into OpenSpec as current requirements.
- Operational setup and testing guidance remain in the maintained docs outside this folder, especially `docs/running.md`, `docs/testing.md`, and `docs/architecture.md`.
