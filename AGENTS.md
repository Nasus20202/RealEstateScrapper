# AGENTS.md

Instructions for agents/developers working in this repository.

## Project Areas

- Backend instructions live in `backend/AGENTS.md`.
- Frontend instructions live in `frontend/AGENTS.md`.

## Rules

- TDD: test → implementation → commit.
- Run the relevant area-specific tests, lint, and formatting before committing.
- No secrets in repo; use environment/config files that are not committed.
- Keep OpenSpec and implementation aligned; do not treat legacy `docs/superpowers/` plans as the source of truth.

## OpenSpec

- Canonical capability specs live in `openspec/specs/`.
- Validate spec changes with `openspec validate --specs`.
- `docs/superpowers/` is a legacy archive; see `docs/superpowers/README.md` for the migration mapping.
- Keep specs grounded in actual shipped behavior unless the user is explicitly proposing a new change.

Documentation: `docs/`

## Documentation

Full technical documentation for the project:

- [`README.md`](README.md) — project overview, quick start, links to docs/
- [`openspec/specs/`](openspec/specs/) — canonical capability specs
- [`docs/architecture.md`](docs/architecture.md) — layered architecture and data flow
- [`docs/running.md`](docs/running.md) — full setup instructions (requirements, database, migrations, API, frontend)
- [`docs/configuration.md`](docs/configuration.md) — all configuration variables (Settings)
- [`docs/adding-a-scraper.md`](docs/adding-a-scraper.md) — how to add a new scraper plugin
- [`docs/testing.md`](docs/testing.md) — test strategy, markers, lint, frontend
- [`docs/scrapers-field-contract.md`](docs/scrapers-field-contract.md) — RawListing field contract per source
- [`docs/superpowers/README.md`](docs/superpowers/README.md) — legacy superpowers to OpenSpec migration note
