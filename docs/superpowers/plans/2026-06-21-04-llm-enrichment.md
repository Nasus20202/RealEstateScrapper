# LLM enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Asynchronously enrich `Listings` with content-optimized descriptions (for search) and generate embeddings (vector of length `EMBEDDING_DIM=768`). Use **pgvector** (database stores the vector, SQLAlchemy does not see it directly — queries go through raw SQL).

**Tech Stack:** OpenAI API (GPT-4o-mini for description enrichment) + OpenAI embeddings API (`text-embedding-3-small`, 1536→768 via dimensions), asyncio, SQLAlchemy 2.0 async.

## Global constraints

- Python 3.14; execution via **uv**. SQLAlchemy 2.0 async. Migrations only via Alembic.
- `EMBEDDING_DIM=768` embedded in code — configurable via `Settings`.
- TDD; `uv run ruff check .` must pass.
- Embeddings stored via raw SQL (SQLAlchemy does not support pgvector directly). Query in Plan 5 via raw SQL + cosine distance.
- OpenAI client with retry logic; each listing enriched independently; parallel via `asyncio.gather` with semaphore (limit concurrency, default 10).
- Re-enrich only when `embedding IS NULL` or `enriched_description IS NULL`.

---

### Task 1: Pgvector column `embedding` + migration 0005 + VectorQueryBuilder

**Files:**
- Create: `src/realestate/db/vector.py`
- Create: `migrations/versions/0005_listing_embedding.py`
- Test: `tests/db/test_vector.py` (or integrate with existing tests)

**Interfaces:**
- `def ensure_vector_extension(conn: Connection) -> None` — `CREATE EXTENSION IF NOT EXISTS vector`.
- `def create_vector_column_op() -> op` — `sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True)` for Alembic.

**Migration 0005:**
- `down_revision="0004"`
- Check `embedding` column: if missing → add column of type `vector(768)`.
- Add optional GIN index for filtering + HNSW index for similarity (HNSW with `vector_cosine_ops`):

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

def upgrade():
    op.create_table_helper(...)  # or explicit:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.add_column("listings", sa.Column("embedding", Vector(768), nullable=True))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_listings_embedding ON listings USING hnsw (embedding vector_cosine_ops)"))

def downgrade():
    op.drop_column("listings", "embedding")
    op.execute(text("DROP INDEX IF EXISTS ix_listings_embedding"))
```

- [ ] **Step 1: Test** — `ensure_vector_extension` works on engine, column can store/read vectors (insert/select via raw SQL).

`tests/db/test_vector.py`:
```python
import numpy as np
from sqlalchemy import text

async def test_vector_roundtrip(engine):
    from realestate.db.vector import ensure_vector_extension
    async with engine.begin() as conn:
        await ensure_vector_extension(conn)
        await conn.execute(text("CREATE TEMP TABLE _vtest (e vector(768))"))
        vec = np.random.rand(768).astype("float32")
        vec_str = "[" + ",".join(str(v) for v in vec) + "]"
        await conn.execute(text("INSERT INTO _vtest VALUES (:v)"), {"v": vec_str})
        row = (await conn.execute(text("SELECT e::text FROM _vtest LIMIT 1"))).scalar()
        assert row.startswith("[")
```

- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement `vector.py`** (`ensure_vector_extension`, `Vector` import from `pgvector.sqlalchemy` — optional if column could be added via `op`).
- [ ] **Step 4: Migration 0005** — idempotent (IF NOT EXISTS for extension and index).
- [ ] **Step 5: PASS.**
- [ ] **Step 6: Commit** (migration + vector helpers + test).

---

### Task 2: `EnrichmentOrchestrator`

**Files:**
- Create: `src/realestate/enrichment/__init__.py`
- Create: `src/realestate/enrichment/openai_client.py`
- Create: `src/realestate/enrichment/orchestrator.py`
- Modify: `src/realestate/enrichment/__init__.py`
- Test: `tests/enrichment/test_orchestrator.py`

**Interfaces:**

`openai_client.py`:
- `EnrichmentClient(api_key: str | None = None)`:
  - `async def enrich_description(listing: Listing) -> str`:
    - Sends to GPT-4o-mini: system prompt "You are an assistant that enriches real estate listings with SEO-friendly descriptions. Output Polish." + listing details (title, description, price, area, rooms, floor, city, district, street).
    - Returns concise (~3 sentences) content-optimized description.
  - `async def generate_embedding(text: str) -> list[float]`:
    - Uses `text-embedding-3-small`, dimensions=768.
    - Retry 3x with exponential backoff.
  - Uses `openai.AsyncOpenAI`.

`orchestrator.py`:
- `EnrichmentOrchestrator(client: EnrichmentClient, session_factory: async_sessionmaker, semaphore: int = 10)`:
  - `async def enrich_pending(limit: int = 50) -> tuple[int, int]` (processed, errors):
    - Query listings WHERE `embedding IS NULL` OR `enriched_description IS NULL` LIMIT `limit`.
    - For each (with semaphore):
      - If `enriched_description` is None → `client.enrich_description(listing)` → `listing.enriched_description`.
      - If `embedding` is None → `client.generate_embedding(enriched_description or listing.title)` → save embedding via raw SQL `UPDATE listings SET embedding = :vec WHERE id = :id`.
    - Return processed/error counts.

- [ ] **Step 1: Tests (`tests/enrichment/test_orchestrator.py`)**

Mock OpenAI client in all tests — do not hit real API.

**Scenarios:**
- Single listing without description nor embedding → processed 1, description set, embedding set.
- Listing that already has both → skipped (return processed 0).
- Listing with description but no embedding → only embedding generated.
- OpenAI call fails for one listing → error counted, remaining listings processed.
- Semaphore limits concurrency (test with 5 listings, semaphore=2 — verify max 2 simultaneous calls via a mock that tracks active calls).

```python
from unittest.mock import AsyncMock, patch

import pytest

from realestate.models import Listing, ListingStatus


class _MockClient:
    def __init__(self):
        self.enrich_calls = []
        self.embed_calls = []

    async def enrich_description(self, listing):
        self.enrich_calls.append(listing.external_id)
        return f"Enriched description for {listing.title}"

    async def generate_embedding(self, text):
        self.embed_calls.append(text[:20])
        return [0.1] * 768
```

- [ ] **Step 2: FAIL** (module not found).
- [ ] **Step 3: Implement** `openai_client.py`:
  - Retry with `tenacity` or simple loop (3x, sleep 1, 2, 4s).
  - Prompt: `"You are a real estate SEO specialist. Write a concise, keyword-rich description (2-3 sentences) in Polish based on the listing data below."`
  - Embedding: `response.data[0].embedding`.

`orchestrator.py`:
  - `select(Listing).where(or_(Listing.embedding.is_(None), Listing.enriched_description.is_(None))).limit(limit)`.
  - Save embedding via raw SQL:
    ```python
    await session.execute(
        text("UPDATE listings SET embedding = :vec WHERE id = :id"),
        {"vec": str(embedding), "id": listing.id}
    )
    ```
  - Semaphore: `asyncio.Semaphore(semaphore)`.

- [ ] **Step 4: PASS.**
- [ ] **Step 5: Full suite + lint.**
- [ ] **Step 6: Commit**

```bash
git add src/realestate/enrichment/ tests/enrichment/
git commit -m "feat: LLM enrichment — description + embedding via OpenAI"
```

---

## Definition of done (Plan 4)
- `embedding` column of type `vector(768)` in the database, HNSW index.
- `EnrichmentOrchestrator.enrich_pending()` enriches listings without description/embedding using GPT-4o-mini and `text-embedding-3-small`.
- Semaphore-controlled concurrency (default 10).
- Retry logic on OpenAI failures; per-listing error isolation.
- All tests with mocked OpenAI pass.
