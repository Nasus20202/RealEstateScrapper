# Testing Strategy

## Backend

### Running

```bash
cd backend
uv run pytest
```

### Configuration

- Framework: **pytest** with **pytest-asyncio** plugin (`auto` mode — all async tests run automatically).
- Integration and E2E tests use **testcontainers** to run PostgreSQL 18 + pgvector in an isolated Docker container. **Docker required.** PostGIS is tested via conditional migration: in the test image without PostGIS, the spatial part is no-op, and the runtime compose uses its own image with PostGIS.
- pytest config: `pyproject.toml` (section `[tool.pytest.ini_options]`).

### Test Structure

```
tests/
├── conftest.py              # Global fixtures (database, engine, session)
├── test_config.py           # Configuration tests (Settings)
├── test_smoke.py            # Smoke tests (imports, health)
├── test_docs_present.py     # Documentation file presence
├── api/                     # HTTP endpoint tests (FastAPI TestClient)
├── db/                      # Model and migration tests
├── e2e/                     # End-to-end tests via HTTP on real pg18
├── enrichment/              # EnrichmentService, DedupService tests
├── events/                  # EventBus / SSE tests
├── fixtures/data/           # Gzipped HTML fixtures for scrapers
├── ingestion/               # IncrementalEngine tests
├── llm/                     # LLMClient, FakeLLM tests
├── repositories/            # Data access layer tests
├── scheduler/               # Scheduler tests
├── scrapers/                # Offline scraper plugin tests
└── search/                  # SearchService tests (hybrid search)
```

### Markers

Tests marked `@pytest.mark.live` require external network access (e.g. real scraping) and are skipped by default. Run them explicitly:

```bash
cd backend
uv run pytest -m live
```

### Testcontainers and Docker

Integration tests start a `pgvector/pgvector:pg18` container via testcontainers. The container starts once per pytest session (session-scoped fixture). The runtime Docker Compose uses a separate `docker/db/Dockerfile` based on `postgres:18.4-trixie` with PostGIS and pgvector. Requirements:

1. Running Docker daemon.
2. Access to Docker Hub (or a local `pgvector/pgvector:pg18` image).

On first run, Docker pulls the image — this may take a while.

### Lint

```bash
cd backend
uv run ruff check .
```

Ruff must be clean before every commit. Configuration: `pyproject.toml` (section `[tool.ruff]`).

### Pyright / type-checking

**Known false positives:** Pyright reports import errors for projects with the `backend/src/` layout (src-layout). These errors are false alerts — they do not block functionality. **Quality gate** is ruff + pytest, not Pyright.

---

## Frontend

### Running Tests

```bash
pnpm --dir frontend exec vitest run
```

The `--run` flag runs vitest in single-run mode (not watch).

### Configuration

- Framework: **Vitest 4** + **@testing-library/react** + **MSW** (Mock Service Worker for API mocking).
- Environment: jsdom 29.
- TypeScript: `tsc -b` does not block tests, but `pnpm --dir frontend build` (= `tsc -b && vite build`) must pass.

### Build

```bash
pnpm --dir frontend build
```

Build validates TypeScript correctness and generates production artifacts in `frontend/dist/`.

### Test Structure

Tests are placed next to components in `frontend/src/` or in `frontend/src/__tests__/`. MSW `handlers` mock backend endpoints — frontend tests do not require a running backend.

---

## Quality Gate Summary

| Command | Purpose | Docker Required |
|---|---|---|
| `uv run pytest` | Backend: all integration and unit tests | yes (testcontainers) |
| `uv run ruff check .` | Python lint | no |
| `pnpm --dir frontend exec vitest run` | Frontend: Vitest | no |
| `pnpm --dir frontend build` | TypeScript validation + build | no |
