# Abstrakcja LLM + wzbogacanie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać konfigurowalną warstwę LLM (OpenAI-compatible, OpenRouter jako default) oraz wzbogacanie ofert: podsumowanie, ekstrakcja cech, embedding (pgvector) i wykrywanie duplikatów — wszystko cache'owane po hashu treści, z miękką degradacją gdy LLM nie jest skonfigurowany.

**Architecture:** Interfejs `LLMClient` (Protocol) niezależny od dostawcy — dwie implementacje: `OpenAICompatClient` (httpx, base_url/api_key/model/embedding_model z konfiguracji) oraz `FakeLLMClient` (deterministyczny, do testów). `EnrichmentService` wywołuje LLM po summary+features+embedding i cache'uje wynik w `llm_analysis` (klucz: `(listing_id, content_hash)`) oraz zapisuje wektor w `listings.embedding`. `DedupService` grupuje te same nieruchomości z różnych portali w `dedup_groups`/`dedup_members`. Brak skonfigurowanego klienta → operacje są no-op (degradacja).

**Tech Stack:** Python 3.14, httpx (klient HTTP, async), SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector, pydantic-settings.

## Global Constraints

- Stack: Python 3.14, SQLAlchemy 2.0 async + asyncpg, PostgreSQL 18 + pgvector, Alembic. Uruchamianie: `uv run`.
- TDD: test → implementacja → commit. Testy DB na realnym kontenerze pg18 (fixture `engine` w `tests/conftest.py`).
- Lint `uv run ruff check .` musi przechodzić. Reguły ruff: `E, F, I, UP, B`; `line-length=100`; StrEnum (nie `(str, Enum)`) bo UP042.
- **Żaden dostawca/model LLM nie jest zaszyty w kodzie.** `base_url`/`api_key`/`model`/`embedding_model` pochodzą wyłącznie z konfiguracji (`pydantic-settings`, `.env`). Domyślny `base_url` może wskazywać OpenRouter, ale `model` i `embedding_model` NIE mają wartości domyślnej — bez nich LLM jest wyłączony.
- Brak sekretów w repo. Zmiany schematu TYLKO przez Alembic.
- Wymiar embeddingu: jedno źródło `realestate.config.get_embedding_dim()` (env `EMBEDDING_DIM`, default 2048). `FakeLLMClient.embed` MUSI zwracać wektory tej długości.
- Pyright/import-resolution błędy to znane false-positives (src-layout) — brama jakości to wyłącznie `ruff` + `pytest`.
- Degradacja: gdy LLM nie jest skonfigurowany, fabryka zwraca `None`, a serwisy wzbogacania są no-op (nie rzucają).

---

### Task 1: Abstrakcja LLM (typy + `LLMClient` Protocol) + `FakeLLMClient`

**Files:**

- Create: `src/realestate/llm/__init__.py` (pusty)
- Create: `src/realestate/llm/base.py`
- Create: `src/realestate/llm/fake.py`
- Test: `tests/llm/__init__.py` (pusty), `tests/llm/test_fake_client.py`

**Interfaces:**

- Consumes: `realestate.config.get_embedding_dim`.
- Produces:
  - `class ChatMessage(BaseModel)`: `role: str`, `content: str`.
  - `class LLMResult(BaseModel)`: `content: str`; `raw: dict | None = None`.
  - `@runtime_checkable class LLMClient(Protocol)`:
    - `async def complete(self, messages: list[ChatMessage], *, response_format: dict | None = None) -> LLMResult: ...`
    - `async def embed(self, texts: list[str]) -> list[list[float]]: ...`
  - `class FakeLLMClient`: deterministyczny klient implementujący `LLMClient`. Konstruktor: `FakeLLMClient(*, completion: str | None = None)`. `complete` zwraca `LLMResult(content=self._completion(messages))`; domyślnie deterministyczny JSON `{"summary": "...", "features": {...}}` zbudowany z ostatniej wiadomości user. `embed` zwraca dla każdego tekstu wektor długości `get_embedding_dim()` wygenerowany deterministycznie z hasha tekstu (wartości w [0,1)).

- [ ] **Step 1: Write the failing test**

```python
# tests/llm/test_fake_client.py
import pytest

from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMClient, LLMResult
from realestate.llm.fake import FakeLLMClient


async def test_fake_client_satisfies_protocol():
    client = FakeLLMClient()
    assert isinstance(client, LLMClient)


async def test_fake_complete_is_deterministic():
    client = FakeLLMClient()
    msgs = [ChatMessage(role="user", content="opis mieszkania")]
    r1 = await client.complete(msgs)
    r2 = await client.complete(msgs)
    assert isinstance(r1, LLMResult)
    assert r1.content == r2.content
    assert r1.content  # niepuste


async def test_fake_complete_with_fixed_completion():
    client = FakeLLMClient(completion='{"summary": "x", "features": {}}')
    r = await client.complete([ChatMessage(role="user", content="cokolwiek")])
    assert r.content == '{"summary": "x", "features": {}}'


async def test_fake_embed_returns_correct_dim_and_deterministic():
    client = FakeLLMClient()
    out1 = await client.embed(["a", "b"])
    out2 = await client.embed(["a", "b"])
    dim = get_embedding_dim()
    assert len(out1) == 2
    assert all(len(v) == dim for v in out1)
    assert out1 == out2  # determinizm
    assert out1[0] != out1[1]  # różne teksty → różne wektory
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/llm/test_fake_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.llm'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/llm/base.py
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMResult(BaseModel):
    content: str
    raw: dict | None = None


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

```python
# src/realestate/llm/fake.py
from __future__ import annotations

import hashlib
import json
import random

from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMResult


class FakeLLMClient:
    """Deterministyczny klient LLM do testów (bez sieci)."""

    def __init__(self, *, completion: str | None = None) -> None:
        self._fixed = completion

    def _completion(self, messages: list[ChatMessage]) -> str:
        if self._fixed is not None:
            return self._fixed
        last = messages[-1].content if messages else ""
        # Deterministyczny "wynik wzbogacenia" jako JSON.
        return json.dumps(
            {
                "summary": f"Streszczenie: {last[:40]}",
                "features": {"liczba_znakow": len(last)},
            },
            ensure_ascii=False,
        )

    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult:
        return LLMResult(content=self._completion(messages))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = get_embedding_dim()
        out: list[list[float]] = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
            rng = random.Random(seed)
            out.append([rng.random() for _ in range(dim)])
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/llm/test_fake_client.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/llm tests/llm
git commit -m "feat: abstrakcja LLM (LLMClient Protocol, LLMResult) + FakeLLMClient"
```

---

### Task 2: Klient OpenAI-compatible (`OpenAICompatClient`) + fabryka + konfiguracja

**Files:**

- Modify: `pyproject.toml` (przenieś `httpx>=0.28` do runtime `dependencies`)
- Modify: `src/realestate/config.py` (dodaj ustawienia LLM)
- Create: `src/realestate/llm/openai_compat.py`
- Create: `src/realestate/llm/factory.py`
- Test: `tests/llm/test_openai_compat.py`, `tests/llm/test_factory.py`

**Interfaces:**

- Consumes: `Settings` (z `config.py`), `ChatMessage`, `LLMResult`, `LLMClient`.
- Produces:
  - W `Settings`: `llm_base_url: str = "https://openrouter.ai/api/v1"`, `llm_api_key: str | None = None`, `llm_model: str | None = None`, `llm_embedding_model: str | None = None`, `llm_timeout_seconds: float = 30.0`, `llm_max_retries: int = 2`. Property `llm_enabled: bool` = wszystkie z (`llm_api_key`, `llm_model`, `llm_embedding_model`) ustawione (truthy).
  - `class OpenAICompatClient`: `__init__(self, *, base_url, api_key, model, embedding_model, timeout=30.0, max_retries=2, client: httpx.AsyncClient | None = None)`. Implementuje `LLMClient`. `complete` → `POST {base_url}/chat/completions`; `embed` → `POST {base_url}/embeddings`. Nagłówek `Authorization: Bearer {api_key}`. Retry na `httpx.HTTPStatusError` (5xx) i `httpx.TransportError` do `max_retries` razy.
  - `def build_client_from_settings(settings: Settings) -> OpenAICompatClient`.
  - `def get_llm_client() -> LLMClient | None`: zwraca `OpenAICompatClient` gdy `settings.llm_enabled`, inaczej `None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/llm/test_openai_compat.py
import httpx
import pytest

from realestate.llm.base import ChatMessage
from realestate.llm.openai_compat import OpenAICompatClient


def _client(handler) -> OpenAICompatClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return OpenAICompatClient(
        base_url="https://example.test/v1",
        api_key="secret-key",
        model="some/chat-model",
        embedding_model="some/embed-model",
        client=http,
    )


async def test_complete_sends_expected_request_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Witaj"}}]},
        )

    client = _client(handler)
    result = await client.complete(
        [ChatMessage(role="user", content="czesc")],
        response_format={"type": "json_object"},
    )
    assert result.content == "Witaj"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["body"]["model"] == "some/chat-model"
    assert captured["body"]["messages"] == [{"role": "user", "content": "czesc"}]
    assert captured["body"]["response_format"] == {"type": "json_object"}


async def test_embed_sends_expected_request_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
        )

    client = _client(handler)
    out = await client.embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://example.test/v1/embeddings"
    assert captured["body"]["model"] == "some/embed-model"
    assert captured["body"]["input"] == ["a", "b"]


async def test_complete_retries_on_server_error_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = _client(handler)
    result = await client.complete([ChatMessage(role="user", content="x")])
    assert result.content == "ok"
    assert calls["n"] == 2
```

```python
# tests/llm/test_factory.py
import pytest

from realestate.config import Settings
from realestate.llm.factory import build_client_from_settings


def _settings(**over) -> Settings:
    base = dict(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        llm_api_key="k",
        llm_model="m",
        llm_embedding_model="e",
    )
    base.update(over)
    return Settings(**base)


def test_llm_enabled_true_when_all_set():
    assert _settings().llm_enabled is True


def test_llm_enabled_false_when_missing_model():
    assert _settings(llm_model=None).llm_enabled is False


def test_build_client_from_settings_uses_config():
    client = build_client_from_settings(_settings(llm_base_url="https://x.test/v1"))
    assert client.base_url == "https://x.test/v1"
    assert client.model == "m"
    assert client.embedding_model == "e"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/llm/test_openai_compat.py tests/llm/test_factory.py -v`
Expected: FAIL — moduły/ustawienia nie istnieją.

- [ ] **Step 3: Write minimal implementation**

W `pyproject.toml` przenieś `httpx>=0.28` z `dev` do `dependencies` (zostaw w obu jeśli prościej — ale runtime jest wymagany). Następnie `uv sync` jeśli potrzeba.

W `src/realestate/config.py` dodaj do klasy `Settings` (po `scraper_wait_until`):

```python
    # --- LLM (konfigurowalny dostawca, OpenAI-compatible). Nic nie hardcodowane. ---
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_embedding_model: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_model and self.llm_embedding_model)
```

```python
# src/realestate/llm/openai_compat.py
from __future__ import annotations

import asyncio

import httpx

from realestate.llm.base import ChatMessage, LLMResult


class OpenAICompatClient:
    """Klient zgodny z OpenAI Chat/Embeddings API (np. OpenRouter)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        embedding_model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _post(self, path: str, payload: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._http().post(
                    f"{self.base_url}{path}", json=payload, headers=self._headers
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code < 500 or attempt == self.max_retries:
                    raise
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise
            await asyncio.sleep(0)  # oddaj sterowanie; brak realnego backoffu w testach
        assert last_exc is not None
        raise last_exc

    async def complete(
        self, messages: list[ChatMessage], *, response_format: dict | None = None
    ) -> LLMResult:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        data = await self._post("/chat/completions", payload)
        content = data["choices"][0]["message"]["content"]
        return LLMResult(content=content, raw=data)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.embedding_model, "input": texts}
        data = await self._post("/embeddings", payload)
        return [item["embedding"] for item in data["data"]]
```

```python
# src/realestate/llm/factory.py
from __future__ import annotations

from realestate.config import Settings, get_settings
from realestate.llm.base import LLMClient
from realestate.llm.openai_compat import OpenAICompatClient


def build_client_from_settings(settings: Settings) -> OpenAICompatClient:
    return OpenAICompatClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model or "",
        embedding_model=settings.llm_embedding_model or "",
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    return build_client_from_settings(settings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/llm/ -v`
Expected: PASS (wszystkie testy llm).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/realestate/config.py src/realestate/llm/openai_compat.py src/realestate/llm/factory.py tests/llm/test_openai_compat.py tests/llm/test_factory.py
git commit -m "feat: OpenAICompatClient (httpx, OpenRouter default) + fabryka + konfiguracja LLM"
```

---

### Task 3: Model `LLMAnalysis` + repozytorium + migracja 0005

**Files:**

- Create: `src/realestate/models/llm_analysis.py`
- Modify: `src/realestate/models/__init__.py` (eksport `LLMAnalysis`)
- Create: `src/realestate/repositories/llm_analysis.py`
- Create: `migrations/versions/0005_llm_analysis.py`
- Test: `tests/db/test_llm_analysis_model.py`, `tests/repositories/test_llm_analysis_repo.py`

**Interfaces:**

- Consumes: `Base`, `Listing` (FK), `ListingRepository` wzorzec.
- Produces:
  - `class LLMAnalysis(Base)` tabela `llm_analysis`: `id PK`, `listing_id FK→listings.id (ondelete CASCADE, index)`, `content_hash: str(64)`, `summary: Text`, `features: JSONB` (typ `sqlalchemy.dialects.postgresql.JSONB`), `model: str(128)`, `created_at: datetime(tz)`. `UniqueConstraint("listing_id", "content_hash", name="uq_analysis_listing_hash")`.
  - `class LLMAnalysisRepository(session)`: `async get(listing_id: int, content_hash: str) -> LLMAnalysis | None`; `async add(analysis: LLMAnalysis) -> LLMAnalysis` (add + flush).
  - Migracja `0005_llm_analysis` (`down_revision="0004"`): tworzy tabelę `llm_analysis` + unikalny indeks/constraint; `downgrade` usuwa tabelę.

- [ ] **Step 1: Write the failing tests**

```python
# tests/db/test_llm_analysis_model.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, LLMAnalysis, Listing
from realestate.models.enums import ListingStatus


async def _make_listing(session: AsyncSession) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(
        source_id="otodom", external_id="x1", url="http://x", title="t",
        raw_hash="h1", status=ListingStatus.ACTIVE, first_seen=now, last_seen=now,
        images=[],
    )
    session.add(listing)
    await session.flush()
    return listing


async def test_llm_analysis_persists(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _make_listing(s)
        s.add(LLMAnalysis(
            listing_id=listing.id, content_hash="h1", summary="streszczenie",
            features={"balkon": True}, model="m", created_at=datetime.now(UTC),
        ))
        await s.flush()
        row = (await s.execute(select(LLMAnalysis))).scalar_one()
        assert row.features == {"balkon": True}
        assert row.summary == "streszczenie"


async def test_llm_analysis_unique_listing_hash(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _make_listing(s)
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="a",
                          features={}, model="m", created_at=datetime.now(UTC)))
        await s.flush()
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="b",
                          features={}, model="m", created_at=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            await s.flush()
```

```python
# tests/repositories/test_llm_analysis_repo.py
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, LLMAnalysis, Listing
from realestate.models.enums import ListingStatus
from realestate.repositories.llm_analysis import LLMAnalysisRepository


async def _listing(s: AsyncSession) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id="y1", url="u", title="t",
                      raw_hash="hh", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_get_returns_none_then_row(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        repo = LLMAnalysisRepository(s)
        assert await repo.get(listing.id, "hh") is None
        await repo.add(LLMAnalysis(listing_id=listing.id, content_hash="hh",
                                   summary="x", features={}, model="m",
                                   created_at=datetime.now(UTC)))
        got = await repo.get(listing.id, "hh")
        assert got is not None and got.summary == "x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/db/test_llm_analysis_model.py tests/repositories/test_llm_analysis_repo.py -v`
Expected: FAIL — `ImportError` (brak `LLMAnalysis`/repo).

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/models/llm_analysis.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from realestate.models.base import Base


class LLMAnalysis(Base):
    __tablename__ = "llm_analysis"
    __table_args__ = (
        UniqueConstraint("listing_id", "content_hash", name="uq_analysis_listing_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    features: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

Dodaj do `src/realestate/models/__init__.py` import i `__all__`:

```python
from realestate.models.llm_analysis import LLMAnalysis
# ... w __all__: "LLMAnalysis",
```

```python
# src/realestate/repositories/llm_analysis.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.llm_analysis import LLMAnalysis


class LLMAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, listing_id: int, content_hash: str) -> LLMAnalysis | None:
        stmt = select(LLMAnalysis).where(
            LLMAnalysis.listing_id == listing_id,
            LLMAnalysis.content_hash == content_hash,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, analysis: LLMAnalysis) -> LLMAnalysis:
        self.session.add(analysis)
        await self.session.flush()
        return analysis
```

Migracja — wzoruj się na istniejącej `migrations/versions/0004_scrape_runs.py` (ten sam styl `op.create_table`):

```python
# migrations/versions/0005_llm_analysis.py
"""llm_analysis

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", "content_hash", name="uq_analysis_listing_hash"),
    )
    op.create_index("ix_llm_analysis_listing_id", "llm_analysis", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_analysis_listing_id", table_name="llm_analysis")
    op.drop_table("llm_analysis")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/db/test_llm_analysis_model.py tests/repositories/test_llm_analysis_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/realestate/models/llm_analysis.py src/realestate/models/__init__.py src/realestate/repositories/llm_analysis.py migrations/versions/0005_llm_analysis.py tests/db/test_llm_analysis_model.py tests/repositories/test_llm_analysis_repo.py
git commit -m "feat: model LLMAnalysis + repozytorium + migracja 0005"
```

---

### Task 4: `EnrichmentService` (summary + features + embedding, cache po hashu, degradacja)

**Files:**

- Create: `src/realestate/enrichment/__init__.py` (pusty)
- Create: `src/realestate/enrichment/prompts.py`
- Create: `src/realestate/enrichment/service.py`
- Test: `tests/enrichment/__init__.py` (pusty), `tests/enrichment/test_enrichment_service.py`

**Interfaces:**

- Consumes: `LLMClient` (lub `None`), `LLMAnalysisRepository`, `LLMAnalysis`, `Listing`, `ListingRepository`, `ChatMessage`.
- Produces:
  - `build_enrichment_messages(listing: Listing) -> list[ChatMessage]` (w `prompts.py`): system + user z polami oferty (title, description, city, district, rooms, area_m2, price). User prosi o JSON `{"summary": str, "features": object}`.
  - `class EnrichmentService(session, client: LLMClient | None, *, model_name: str = "unknown")`:
    - `async def enrich_listing(self, listing: Listing, *, now: datetime) -> bool`:
      - jeśli `client is None` → zwróć `False` (degradacja, no-op).
      - cache: `existing = await LLMAnalysisRepository(session).get(listing.id, listing.raw_hash)`; jeśli `existing is not None and listing.embedding is not None` → zwróć `False` (cache hit, nic nie rób).
      - w przeciwnym razie: `result = await client.complete(build_enrichment_messages(listing), response_format={"type": "json_object"})`; sparsuj `data = json.loads(result.content)`; `summary = str(data.get("summary", ""))`, `features = data.get("features", {})` (jeśli nie dict → `{}`).
      - `vectors = await client.embed([_embedding_text(listing, summary)])`; `listing.embedding = vectors[0]`.
      - jeśli `existing is None`: `repo.add(LLMAnalysis(listing_id=listing.id, content_hash=listing.raw_hash, summary=summary, features=features, model=self.model_name, created_at=now))`. Jeśli `existing is not None` (był wpis, ale brak embeddingu) → zaktualizuj `existing.summary/features/created_at` oraz ustaw embedding (nie twórz duplikatu).
      - `await session.flush()`; zwróć `True`.
    - `async def enrich_many(self, listings: list[Listing], *, now: datetime) -> int`: pętla po `enrich_listing`, zwróć liczbę faktycznie wzbogaconych (True).
  - `_embedding_text(listing, summary) -> str` (helper, może być w service.py): łączy `title + district/city + summary + opis`.

- [ ] **Step 1: Write the failing test**

```python
# tests/enrichment/test_enrichment_service.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.service import EnrichmentService
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, LLMAnalysis, Listing
from realestate.models.enums import ListingStatus


class _SpyClient:
    """Liczy wywołania; zwraca stały JSON i deterministyczny embedding dim=3."""
    def __init__(self):
        self.complete_calls = 0
        self.embed_calls = 0

    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        self.complete_calls += 1
        return LLMResult(content='{"summary": "ok", "features": {"balkon": true}}')

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


async def _listing(s: AsyncSession, *, raw_hash="h1") -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id="e1", url="u", title="Mieszkanie",
                      description="ladne", city="Gdansk", district="Wrzeszcz",
                      rooms=3, area_m2=60.0, raw_hash=raw_hash,
                      status=ListingStatus.ACTIVE, first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_enrich_creates_analysis_and_sets_embedding(engine, monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "3")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        client = _SpyClient()
        svc = EnrichmentService(s, client, model_name="test-model")
        did = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did is True
        assert client.complete_calls == 1 and client.embed_calls == 1
        row = (await s.execute(select(LLMAnalysis))).scalar_one()
        assert row.summary == "ok"
        assert row.features == {"balkon": True}
        assert listing.embedding is not None
        assert list(listing.embedding) == [0.1, 0.2, 0.3]


async def test_enrich_is_cached_on_second_call(engine, monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "3")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        client = _SpyClient()
        svc = EnrichmentService(s, client, model_name="test-model")
        await svc.enrich_listing(listing, now=datetime.now(UTC))
        did2 = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did2 is False
        assert client.complete_calls == 1  # bez ponownego wywołania
        count = (await s.execute(select(func.count()).select_from(LLMAnalysis))).scalar_one()
        assert count == 1


async def test_enrich_is_noop_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        svc = EnrichmentService(s, None)
        did = await svc.enrich_listing(listing, now=datetime.now(UTC))
        assert did is False
        count = (await s.execute(select(func.count()).select_from(LLMAnalysis))).scalar_one()
        assert count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/enrichment/test_enrichment_service.py -v`
Expected: FAIL — brak modułu `realestate.enrichment`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/enrichment/prompts.py
from __future__ import annotations

from realestate.llm.base import ChatMessage
from realestate.models.listing import Listing

_SYSTEM = (
    "Jesteś asystentem analizującym oferty nieruchomości. "
    "Zwracasz wyłącznie obiekt JSON o kluczach: "
    '"summary" (zwięzłe polskie streszczenie, max 2 zdania) oraz '
    '"features" (obiekt cech wywnioskowanych z tekstu, np. balkon, stan, winda).'
)


def build_enrichment_messages(listing: Listing) -> list[ChatMessage]:
    parts = [
        f"Tytuł: {listing.title}",
        f"Miasto: {listing.city or '-'}",
        f"Dzielnica: {listing.district or '-'}",
        f"Pokoje: {listing.rooms if listing.rooms is not None else '-'}",
        f"Metraż (m2): {listing.area_m2 if listing.area_m2 is not None else '-'}",
        f"Cena: {listing.price if listing.price is not None else '-'}",
        f"Opis: {listing.description or '-'}",
    ]
    return [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content="\n".join(parts)),
    ]
```

```python
# src/realestate/enrichment/service.py
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.prompts import build_enrichment_messages
from realestate.llm.base import LLMClient
from realestate.models.listing import Listing
from realestate.models.llm_analysis import LLMAnalysis
from realestate.repositories.llm_analysis import LLMAnalysisRepository


def _embedding_text(listing: Listing, summary: str) -> str:
    return " ".join(
        x for x in [
            listing.title,
            listing.district or listing.city or "",
            summary,
            listing.description or "",
        ] if x
    )


class EnrichmentService:
    def __init__(
        self, session: AsyncSession, client: LLMClient | None, *, model_name: str = "unknown"
    ) -> None:
        self.session = session
        self.client = client
        self.model_name = model_name

    async def enrich_listing(self, listing: Listing, *, now: datetime) -> bool:
        if self.client is None:
            return False
        repo = LLMAnalysisRepository(self.session)
        existing = await repo.get(listing.id, listing.raw_hash)
        if existing is not None and listing.embedding is not None:
            return False

        result = await self.client.complete(
            build_enrichment_messages(listing), response_format={"type": "json_object"}
        )
        try:
            data = json.loads(result.content)
        except (ValueError, TypeError):
            data = {}
        summary = str(data.get("summary", ""))
        features = data.get("features", {})
        if not isinstance(features, dict):
            features = {}

        vectors = await self.client.embed([_embedding_text(listing, summary)])
        listing.embedding = vectors[0]

        if existing is None:
            await repo.add(
                LLMAnalysis(
                    listing_id=listing.id,
                    content_hash=listing.raw_hash,
                    summary=summary,
                    features=features,
                    model=self.model_name,
                    created_at=now,
                )
            )
        else:
            existing.summary = summary
            existing.features = features
            existing.created_at = now

        await self.session.flush()
        return True

    async def enrich_many(self, listings: list[Listing], *, now: datetime) -> int:
        n = 0
        for listing in listings:
            if await self.enrich_listing(listing, now=now):
                n += 1
        return n
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/enrichment/test_enrichment_service.py -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/enrichment tests/enrichment
git commit -m "feat: EnrichmentService (summary+features+embedding, cache po hashu, degradacja)"
```

---

### Task 5: Modele `DedupGroup`/`DedupMember` + migracja 0006

**Files:**

- Create: `src/realestate/models/dedup.py`
- Modify: `src/realestate/models/__init__.py` (eksport `DedupGroup`, `DedupMember`)
- Create: `migrations/versions/0006_dedup.py`
- Test: `tests/db/test_dedup_models.py`

**Interfaces:**

- Consumes: `Base`, `Listing` (FK).
- Produces:
  - `class DedupGroup(Base)` tabela `dedup_groups`: `id PK`, `created_at: datetime(tz)`. Relacja `members: list[DedupMember]` (cascade all, delete-orphan).
  - `class DedupMember(Base)` tabela `dedup_members`: `id PK`, `group_id FK→dedup_groups.id (CASCADE, index)`, `listing_id FK→listings.id (CASCADE)`, `UniqueConstraint("listing_id", name="uq_dedup_member_listing")` (oferta należy do co najwyżej jednej grupy). Relacja `group: DedupGroup` (back_populates).
  - Migracja `0006_dedup` (`down_revision="0005"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/db/test_dedup_models.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, DedupGroup, DedupMember, Listing
from realestate.models.enums import ListingStatus


async def _listing(s, ext) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title="t",
                      raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_dedup_group_with_members(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        g = DedupGroup(created_at=datetime.now(UTC))
        g.members = [DedupMember(listing_id=l1.id), DedupMember(listing_id=l2.id)]
        s.add(g)
        await s.flush()
        loaded = (await s.execute(select(DedupMember))).scalars().all()
        assert len(loaded) == 2


async def test_listing_in_one_group_only(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "c")
        g1 = DedupGroup(created_at=datetime.now(UTC))
        g1.members = [DedupMember(listing_id=l1.id)]
        s.add(g1)
        await s.flush()
        g2 = DedupGroup(created_at=datetime.now(UTC))
        g2.members = [DedupMember(listing_id=l1.id)]
        s.add(g2)
        with pytest.raises(IntegrityError):
            await s.flush()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/db/test_dedup_models.py -v`
Expected: FAIL — brak modeli.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/models/dedup.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from realestate.models.base import Base


class DedupGroup(Base):
    __tablename__ = "dedup_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    members: Mapped[list[DedupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DedupMember(Base):
    __tablename__ = "dedup_members"
    __table_args__ = (
        UniqueConstraint("listing_id", name="uq_dedup_member_listing"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("dedup_groups.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))

    group: Mapped[DedupGroup] = relationship(back_populates="members")
```

Dodaj do `src/realestate/models/__init__.py`:

```python
from realestate.models.dedup import DedupGroup, DedupMember
# ... w __all__: "DedupGroup", "DedupMember",
```

```python
# migrations/versions/0006_dedup.py
"""dedup groups/members

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dedup_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "dedup_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["dedup_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", name="uq_dedup_member_listing"),
    )
    op.create_index("ix_dedup_members_group_id", "dedup_members", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_dedup_members_group_id", table_name="dedup_members")
    op.drop_table("dedup_members")
    op.drop_table("dedup_groups")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/db/test_dedup_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/realestate/models/dedup.py src/realestate/models/__init__.py migrations/versions/0006_dedup.py tests/db/test_dedup_models.py
git commit -m "feat: modele DedupGroup/DedupMember + migracja 0006"
```

---

### Task 6: `DedupService.find_duplicates` + utrwalanie grup (degradacja)

**Files:**

- Create: `src/realestate/enrichment/dedup.py`
- Test: `tests/enrichment/test_dedup_service.py`

**Interfaces:**

- Consumes: `LLMClient | None`, `Listing`, `DedupGroup`, `DedupMember`, `ChatMessage`.
- Produces:
  - `build_dedup_messages(listings: list[Listing]) -> list[ChatMessage]`: prosi LLM o pogrupowanie ofert (po `id`) reprezentujących TĘ SAMĄ nieruchomość; format odpowiedzi JSON `{"groups": [[id, id], ...]}` (tylko grupy 2+).
  - `class DedupService(session, client: LLMClient | None)`:
    - `async def find_duplicate_groups(self, listings: list[Listing]) -> list[list[int]]`: gdy `client is None` lub `< 2` ofert → `[]`. W przeciwnym razie `complete(..., response_format={"type":"json_object"})`, sparsuj `groups`, odfiltruj grupy o długości < 2 oraz id spoza wejścia; zwróć listę list `listing_id`.
    - `async def persist_groups(self, groups: list[list[int]], *, now: datetime) -> int`: dla każdej grupy utwórz `DedupGroup` + `DedupMember` per id; `flush`; zwróć liczbę utworzonych grup. (Zakładamy oferty jeszcze nieprzypisane — unikalność `listing_id` to zabezpiecza.)
    - `async def run(self, listings: list[Listing], *, now: datetime) -> int`: `find_duplicate_groups` → `persist_groups`.

- [ ] **Step 1: Write the failing test**

```python
# tests/enrichment/test_dedup_service.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.enrichment.dedup import DedupService
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, DedupGroup, DedupMember, Listing
from realestate.models.enums import ListingStatus


class _GroupingClient:
    def __init__(self, groups):
        self._groups = groups
    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        import json
        return LLMResult(content=json.dumps({"groups": self._groups}))
    async def embed(self, texts):  # pragma: no cover - nieużywane
        return [[0.0] for _ in texts]


async def _listing(s, ext) -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title="t",
                      raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_find_and_persist_groups(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        l3 = await _listing(s, "c")
        client = _GroupingClient([[l1.id, l2.id]])  # l3 sam, nie grupowany
        svc = DedupService(s, client)
        created = await svc.run([l1, l2, l3], now=datetime.now(UTC))
        assert created == 1
        groups = (await s.execute(select(func.count()).select_from(DedupGroup))).scalar_one()
        members = (await s.execute(select(func.count()).select_from(DedupMember))).scalar_one()
        assert groups == 1 and members == 2


async def test_filters_singletons_and_unknown_ids(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        client = _GroupingClient([[l1.id], [l2.id, 99999]])  # singleton + obce id
        svc = DedupService(s, client)
        groups = await svc.find_duplicate_groups([l1, l2])
        assert groups == []  # [l1] singleton odpada; [l2,99999] -> [l2] singleton odpada


async def test_noop_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        l1 = await _listing(s, "a")
        l2 = await _listing(s, "b")
        svc = DedupService(s, None)
        assert await svc.run([l1, l2], now=datetime.now(UTC)) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/enrichment/test_dedup_service.py -v`
Expected: FAIL — brak `realestate.enrichment.dedup`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/enrichment/dedup.py
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from realestate.llm.base import ChatMessage, LLMClient
from realestate.models.dedup import DedupGroup, DedupMember
from realestate.models.listing import Listing

_SYSTEM = (
    "Otrzymasz listę ofert nieruchomości z różnych portali. Zgrupuj te, które "
    "opisują TĘ SAMĄ fizyczną nieruchomość. Zwróć wyłącznie JSON: "
    '{"groups": [[id, id, ...], ...]} — tylko grupy o 2+ elementach.'
)


def build_dedup_messages(listings: list[Listing]) -> list[ChatMessage]:
    lines = []
    for listing in listings:
        lines.append(
            f"id={listing.id} | {listing.title} | {listing.city or '-'}/"
            f"{listing.district or '-'} | {listing.area_m2 or '-'} m2 | "
            f"cena={listing.price if listing.price is not None else '-'} | "
            f"{listing.url}"
        )
    return [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content="\n".join(lines)),
    ]


class DedupService:
    def __init__(self, session: AsyncSession, client: LLMClient | None) -> None:
        self.session = session
        self.client = client

    async def find_duplicate_groups(self, listings: list[Listing]) -> list[list[int]]:
        if self.client is None or len(listings) < 2:
            return []
        valid_ids = {listing.id for listing in listings}
        result = await self.client.complete(
            build_dedup_messages(listings), response_format={"type": "json_object"}
        )
        try:
            data = json.loads(result.content)
        except (ValueError, TypeError):
            return []
        raw_groups = data.get("groups", [])
        groups: list[list[int]] = []
        for grp in raw_groups:
            if not isinstance(grp, list):
                continue
            members = [gid for gid in grp if gid in valid_ids]
            if len(members) >= 2:
                groups.append(members)
        return groups

    async def persist_groups(self, groups: list[list[int]], *, now: datetime) -> int:
        created = 0
        for members in groups:
            group = DedupGroup(created_at=now)
            group.members = [DedupMember(listing_id=lid) for lid in members]
            self.session.add(group)
            created += 1
        await self.session.flush()
        return created

    async def run(self, listings: list[Listing], *, now: datetime) -> int:
        groups = await self.find_duplicate_groups(listings)
        return await self.persist_groups(groups, now=now)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/enrichment/test_dedup_service.py -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Pełny zestaw + lint**

Run: `uv run pytest && uv run ruff check .`
Expected: wszystko zielone, ruff czysty.

- [ ] **Step 6: Commit**

```bash
git add src/realestate/enrichment/dedup.py tests/enrichment/test_dedup_service.py
git commit -m "feat: DedupService (grupowanie duplikatów przez LLM + utrwalanie, degradacja)"
```

---

## Definicja ukończenia (Plan 4)

- `uv run pytest` zielony; `uv run ruff check .` bez błędów.
- `LLMClient` (Protocol) + dwie implementacje: `OpenAICompatClient` (httpx, base_url/api_key/model/embedding_model z konfiguracji, OpenRouter jako domyślny base_url, retry) oraz `FakeLLMClient` (deterministyczny). Żaden model/dostawca nie jest zaszyty.
- Fabryka `get_llm_client()` zwraca `None` gdy LLM niewłączony (degradacja).
- `llm_analysis` (cache per `(listing_id, content_hash)`) + migracja 0005; `dedup_groups`/`dedup_members` + migracja 0006.
- `EnrichmentService`: summary + features + embedding (pgvector), cache po hashu treści, no-op bez klienta.
- `DedupService`: grupowanie duplikatów przez LLM + utrwalanie grup, no-op bez klienta.
