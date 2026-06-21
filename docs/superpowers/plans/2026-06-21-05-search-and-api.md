# Wyszukiwanie hybrydowe + REST API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Udostępnić dane przez REST API (FastAPI): wyszukiwanie hybrydowe ofert (twarde filtry SQL → kandydaci wektorowi pgvector → rerank LLM, z degradacją do rankingu regułowego), szczegóły oferty, ręczny trigger scrapingu + statusy przebiegów, zapisane wyszukiwania, ulubione oraz odczyt/zapis ustawień.

**Architecture:** Warstwa serwisowa `SearchService` realizuje wyszukiwanie hybrydowe na bazie istniejących repozytoriów i (opcjonalnego) `LLMClient`; bez klienta degraduje do rankingu regułowego (cena/m²). FastAPI montuje endpointy z wstrzykiwaniem zależności (silnik/sesja na `app.state`, zależności nadpisywalne w testach przez `dependency_overrides`). Nowe tabele `saved_searches`, `favorites`, `app_settings` (migracja 0007). Scheduler i SSE są POZA zakresem tego planu (kolejny plan).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async + asyncpg, pgvector, Alembic, httpx (ASGITransport w testach), pydantic v2.

## Global Constraints

- Stack: Python 3.14, SQLAlchemy 2.0 async + asyncpg, PostgreSQL 18 + pgvector, Alembic. Uruchamianie: `uv run`.
- TDD: test → implementacja → commit. Testy DB i API na realnym kontenerze pg18 (fixture `engine` w `tests/conftest.py`). Testy API używają `httpx.ASGITransport` + `AsyncClient` i `app.dependency_overrides` (wzór: `tests/api/test_health.py`).
- Lint `uv run ruff check .` musi przechodzić (E,F,I,UP,B; line-length 100; StrEnum dla enumów).
- Zmiany schematu TYLKO przez Alembic. Migracja `0007`, `down_revision="0006"`. Łańcuch migracji musi mieć jedną głowę.
- LLM jest opcjonalny: gdy `get_llm_client()` zwróci `None`, wyszukiwanie degraduje do rankingu regułowego (bez wektorów i bez reranku). NIC dotyczące dostawcy/modelu nie jest hardcodowane.
- Brak sekretów w odpowiedziach API: `GET /settings` NIGDY nie zwraca `llm_api_key` — tylko flagę `llm_api_key_set: bool`.
- Wymiar embeddingu: `get_embedding_dim()` (jedno źródło). Testy konstruujące wektory używają `get_embedding_dim()` do długości.
- Pyright/import-resolution błędy to znane false-positives (src-layout) — brama jakości to `ruff` + `pytest`.

---

### Task 1: Modele `SavedSearch`/`Favorite`/`AppSetting` + repozytoria + migracja 0007

**Files:**
- Create: `src/realestate/models/user_data.py`
- Modify: `src/realestate/models/__init__.py` (eksport `SavedSearch`, `Favorite`, `AppSetting`)
- Create: `src/realestate/repositories/user_data.py`
- Create: `migrations/versions/0007_user_data.py`
- Test: `tests/db/test_user_data_models.py`, `tests/repositories/test_user_data_repos.py`

**Interfaces:**
- Consumes: `Base`, `Listing` (FK).
- Produces:
  - `class SavedSearch(Base)` tabela `saved_searches`: `id PK`, `name: str(128)`, `filters: JSONB` (default dict), `nl_query: str|None` (Text), `created_at: datetime(tz)`.
  - `class Favorite(Base)` tabela `favorites`: `id PK`, `listing_id FK→listings.id (CASCADE)`, `created_at: datetime(tz)`, `UniqueConstraint("listing_id", name="uq_favorite_listing")`.
  - `class AppSetting(Base)` tabela `app_settings`: `key: str(64) PK`, `value: JSONB`.
  - `class SavedSearchRepository(session)`: `async list_all() -> list[SavedSearch]`; `async get(id) -> SavedSearch|None`; `async add(s) -> SavedSearch`; `async delete(id) -> bool`.
  - `class FavoriteRepository(session)`: `async list_all() -> list[Favorite]`; `async add(listing_id) -> Favorite` (idempotentne: jeśli istnieje, zwróć istniejący); `async delete(listing_id) -> bool`; `async exists(listing_id) -> bool`.
  - `class AppSettingRepository(session)`: `async get(key) -> dict|None` (zwraca `value`); `async set(key, value: dict) -> None` (upsert); `async all() -> dict[str, dict]`.
  - Migracja `0007_user_data` (`down_revision="0006"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/db/test_user_data_models.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import AppSetting, Base, Favorite, Listing, SavedSearch
from realestate.models.enums import ListingStatus


async def _listing(s, ext="a") -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title="t",
                      raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_saved_search_and_app_setting_persist(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add(SavedSearch(name="tanie 2pok", filters={"max_price": 500000, "min_rooms": 2},
                          nl_query="blisko morza", created_at=datetime.now(UTC)))
        s.add(AppSetting(key="scheduler_interval_minutes", value={"v": 60}))
        await s.flush()
        ss = (await s.execute(select(SavedSearch))).scalar_one()
        assert ss.filters["max_price"] == 500000
        setting = (await s.execute(select(AppSetting))).scalar_one()
        assert setting.value == {"v": 60}


async def test_favorite_unique(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        s.add(Favorite(listing_id=listing.id, created_at=datetime.now(UTC)))
        await s.flush()
        s.add(Favorite(listing_id=listing.id, created_at=datetime.now(UTC)))
        with pytest.raises(IntegrityError):
            await s.flush()
```

```python
# tests/repositories/test_user_data_repos.py
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing, SavedSearch
from realestate.models.enums import ListingStatus
from realestate.repositories.user_data import (
    AppSettingRepository,
    FavoriteRepository,
    SavedSearchRepository,
)


async def _listing(s, ext="a") -> Listing:
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title="t",
                      raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    s.add(listing)
    await s.flush()
    return listing


async def test_saved_search_repo_crud(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        repo = SavedSearchRepository(s)
        created = await repo.add(SavedSearch(name="x", filters={}, nl_query=None,
                                             created_at=datetime.now(UTC)))
        assert await repo.get(created.id) is not None
        assert len(await repo.list_all()) == 1
        assert await repo.delete(created.id) is True
        assert await repo.get(created.id) is None


async def test_favorite_repo_idempotent_add_and_delete(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        listing = await _listing(s)
        repo = FavoriteRepository(s)
        await repo.add(listing.id)
        await repo.add(listing.id)  # idempotentne
        assert await repo.exists(listing.id) is True
        assert len(await repo.list_all()) == 1
        assert await repo.delete(listing.id) is True
        assert await repo.exists(listing.id) is False


async def test_app_setting_repo_upsert(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        repo = AppSettingRepository(s)
        assert await repo.get("k") is None
        await repo.set("k", {"v": 1})
        await repo.set("k", {"v": 2})  # upsert
        assert await repo.get("k") == {"v": 2}
        assert (await repo.all())["k"] == {"v": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/db/test_user_data_models.py tests/repositories/test_user_data_repos.py -v`
Expected: FAIL — brak modeli/repo.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/models/user_data.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from realestate.models.base import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    nl_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_favorite_listing"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
```

Dodaj do `src/realestate/models/__init__.py` import i `__all__`: `SavedSearch`, `Favorite`, `AppSetting`.

```python
# src/realestate/repositories/user_data.py
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.user_data import AppSetting, Favorite, SavedSearch


class SavedSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[SavedSearch]:
        rows = (await self.session.execute(
            select(SavedSearch).order_by(SavedSearch.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def get(self, search_id: int) -> SavedSearch | None:
        return await self.session.get(SavedSearch, search_id)

    async def add(self, search: SavedSearch) -> SavedSearch:
        self.session.add(search)
        await self.session.flush()
        return search

    async def delete(self, search_id: int) -> bool:
        obj = await self.session.get(SavedSearch, search_id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Favorite]:
        rows = (await self.session.execute(
            select(Favorite).order_by(Favorite.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def exists(self, listing_id: int) -> bool:
        row = (await self.session.execute(
            select(Favorite.id).where(Favorite.listing_id == listing_id)
        )).scalar_one_or_none()
        return row is not None

    async def add(self, listing_id: int) -> Favorite:
        from datetime import UTC, datetime
        existing = (await self.session.execute(
            select(Favorite).where(Favorite.listing_id == listing_id)
        )).scalar_one_or_none()
        if existing is not None:
            return existing
        fav = Favorite(listing_id=listing_id, created_at=datetime.now(UTC))
        self.session.add(fav)
        await self.session.flush()
        return fav

    async def delete(self, listing_id: int) -> bool:
        result = await self.session.execute(
            sa_delete(Favorite).where(Favorite.listing_id == listing_id)
        )
        await self.session.flush()
        return result.rowcount > 0


class AppSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> dict | None:
        obj = await self.session.get(AppSetting, key)
        return obj.value if obj is not None else None

    async def set(self, key: str, value: dict) -> None:
        stmt = pg_insert(AppSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        await self.session.execute(stmt)
        await self.session.flush()

    async def all(self) -> dict[str, dict]:
        rows = (await self.session.execute(select(AppSetting))).scalars().all()
        return {row.key: row.value for row in rows}
```

```python
# migrations/versions/0007_user_data.py
"""saved_searches, favorites, app_settings

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column("nl_query", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", name="uq_favorite_listing"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("favorites")
    op.drop_table("saved_searches")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/db/test_user_data_models.py tests/repositories/test_user_data_repos.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/realestate/models/user_data.py src/realestate/models/__init__.py src/realestate/repositories/user_data.py migrations/versions/0007_user_data.py tests/db/test_user_data_models.py tests/repositories/test_user_data_repos.py
git commit -m "feat: modele SavedSearch/Favorite/AppSetting + repozytoria + migracja 0007"
```

---

### Task 2: `SearchService` — twarde filtry SQL + ranking regułowy (degradacja)

**Files:**
- Create: `src/realestate/search/__init__.py` (pusty)
- Create: `src/realestate/search/filters.py`
- Create: `src/realestate/search/service.py`
- Test: `tests/search/__init__.py` (pusty), `tests/search/test_search_filters.py`

**Interfaces:**
- Consumes: `Listing`, `ListingStatus`, `AsyncSession`.
- Produces:
  - `class ListingFilters(BaseModel)`: `city: str|None=None`, `districts: list[str]|None=None`, `min_price: int|None`, `max_price: int|None`, `min_area: float|None`, `max_area: float|None`, `min_rooms: int|None`, `max_rooms: int|None`, `market: str|None`, `nl_query: str|None=None`.
  - `class RankedListing(BaseModel)`: `listing: <ORM Listing — arbitrary_types_allowed>`, `score: float|None=None`, `reason: str|None=None`. (Użyj `model_config = ConfigDict(arbitrary_types_allowed=True)`.)
  - `class SearchService(session, client=None)` — w tym tasku `client` jest przyjmowany ale NIE używany (degradacja regułowa). 
    - `async def search(self, filters: ListingFilters, *, limit: int = 50, offset: int = 0) -> tuple[list[RankedListing], int]`:
      - buduje zapytanie po `Listing.status == ACTIVE` + warunki z filtrów (`apply_filters`).
      - ranking regułowy: `ORDER BY price_per_m2 ASC NULLS LAST, last_seen DESC`.
      - zwraca `(items, total)` gdzie `total` = liczba pasujących (przed paginacją), `items` = po `limit/offset`, każdy z `score=None, reason=None`.
  - `def apply_filters(stmt, filters: ListingFilters)` (w `filters.py`): dokłada `where(...)` do `select(Listing)` na podstawie ustawionych pól (None pomijane). `districts` → `Listing.district.in_(...)`; `market` → porównanie z `MarketType(filters.market)` jeśli poprawne, inaczej warunek pomijany. `nl_query` NIE jest filtrem SQL (ignorowany tutaj).

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_search_filters.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus, MarketType
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService


async def _listing(s, *, ext, price, area, rooms, district, status=ListingStatus.ACTIVE):
    now = datetime.now(UTC)
    ppm2 = Decimal(price) / Decimal(str(area)) if area else None
    listing = Listing(
        source_id="otodom", external_id=ext, url="u", title=f"oferta {ext}",
        price=Decimal(price), price_per_m2=ppm2, area_m2=area, rooms=rooms,
        district=district, city="Gdansk", market=MarketType.SECONDARY,
        raw_hash="h" + ext, status=status, first_seen=now, last_seen=now, images=[],
    )
    s.add(listing)
    await s.flush()
    return listing


async def test_hard_filters_and_rule_ranking(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        await _listing(s, ext="cheap", price=400000, area=50, rooms=2, district="Wrzeszcz")
        await _listing(s, ext="expensive", price=900000, area=50, rooms=3, district="Oliwa")
        await _listing(s, ext="toobig", price=300000, area=120, rooms=5, district="Wrzeszcz")
        await _listing(s, ext="gone", price=350000, area=50, rooms=2, district="Wrzeszcz",
                       status=ListingStatus.GONE)
        svc = SearchService(s)
        filters = ListingFilters(max_price=500000, min_rooms=2, districts=["Wrzeszcz", "Oliwa"])
        items, total = await svc.search(filters, limit=10, offset=0)
        ids = [r.listing.external_id for r in items]
        # cheap (400k, 2pok, Wrzeszcz) pasuje; expensive odpada (cena); toobig odpada (5pok>... nie,
        # min_rooms=2 ok, ale cena 300k ok, district Wrzeszcz ok) -> faktycznie pasuje!
        assert "cheap" in ids
        assert "toobig" in ids
        assert "expensive" not in ids  # cena > max
        assert "gone" not in ids       # nieaktywne
        assert total == 2
        # ranking regułowy: price_per_m2 rosnąco -> toobig (2500) przed cheap (8000)
        assert ids[0] == "toobig"


async def test_pagination(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        for i in range(5):
            await _listing(s, ext=f"l{i}", price=300000 + i, area=50, rooms=2, district="X")
        svc = SearchService(s)
        items, total = await svc.search(ListingFilters(), limit=2, offset=0)
        assert total == 5 and len(items) == 2
        items2, _ = await svc.search(ListingFilters(), limit=2, offset=4)
        assert len(items2) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/search/test_search_filters.py -v`
Expected: FAIL — brak modułu `realestate.search`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/search/filters.py
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Select

from realestate.models.enums import MarketType
from realestate.models.listing import Listing


class ListingFilters(BaseModel):
    city: str | None = None
    districts: list[str] | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None
    nl_query: str | None = None


def apply_filters(stmt: Select, filters: ListingFilters) -> Select:
    if filters.city:
        stmt = stmt.where(Listing.city == filters.city)
    if filters.districts:
        stmt = stmt.where(Listing.district.in_(filters.districts))
    if filters.min_price is not None:
        stmt = stmt.where(Listing.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Listing.price <= filters.max_price)
    if filters.min_area is not None:
        stmt = stmt.where(Listing.area_m2 >= filters.min_area)
    if filters.max_area is not None:
        stmt = stmt.where(Listing.area_m2 <= filters.max_area)
    if filters.min_rooms is not None:
        stmt = stmt.where(Listing.rooms >= filters.min_rooms)
    if filters.max_rooms is not None:
        stmt = stmt.where(Listing.rooms <= filters.max_rooms)
    if filters.market:
        try:
            stmt = stmt.where(Listing.market == MarketType(filters.market))
        except ValueError:
            pass
    return stmt
```

```python
# src/realestate/search/service.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.search.filters import ListingFilters, apply_filters


class RankedListing(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    listing: Listing
    score: float | None = None
    reason: str | None = None


class SearchService:
    def __init__(self, session: AsyncSession, client=None) -> None:
        self.session = session
        self.client = client

    async def search(
        self, filters: ListingFilters, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[RankedListing], int]:
        base = apply_filters(
            select(Listing).where(Listing.status == ListingStatus.ACTIVE), filters
        )
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = (
            base.order_by(
                Listing.price_per_m2.asc().nulls_last(),
                Listing.last_seen.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [RankedListing(listing=row) for row in rows], total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/search/test_search_filters.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/search/__init__.py src/realestate/search/filters.py src/realestate/search/service.py tests/search/__init__.py tests/search/test_search_filters.py
git commit -m "feat: SearchService — twarde filtry SQL + ranking regułowy"
```

---

### Task 3: Funkcje LLM wyszukiwania — `parse_nl_query` + `match_and_rank`

**Files:**
- Create: `src/realestate/search/llm_search.py`
- Test: `tests/search/test_llm_search.py`

**Interfaces:**
- Consumes: `LLMClient`, `ChatMessage`, `Listing`.
- Produces:
  - `class RankedMatch(BaseModel)`: `listing_id: int`, `score: float`, `reason: str`.
  - `async def parse_nl_query(client: LLMClient, text: str) -> dict`: prosi LLM o JSON ze strukturalnymi podpowiedziami filtrów (np. `{"max_price":..., "min_rooms":..., "districts":[...]}`); parsuje bezpiecznie (zły/nie-dict JSON → `{}`); zwraca tylko klucze będące podzbiorem dozwolonych (`max_price,min_price,min_rooms,max_rooms,min_area,max_area,districts,market,city`).
  - `async def match_and_rank(client: LLMClient, candidates: list[Listing], nl_preferences: str) -> list[RankedMatch]`: buduje prompt z listą kandydatów (`id`, tytuł, cechy, cena), prosi o JSON `{"matches":[{"listing_id":int,"score":0-100,"reason":str}]}`; parsuje bezpiecznie; odfiltrowuje `listing_id` spoza kandydatów; ogranicza `score` do [0,100]; zwraca posortowane malejąco po `score`. Zły JSON → `[]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_llm_search.py
from datetime import UTC, datetime

import pytest

from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Listing
from realestate.models.enums import ListingStatus
from realestate.search.llm_search import RankedMatch, match_and_rank, parse_nl_query


class _Client:
    def __init__(self, content):
        self._content = content
    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        return LLMResult(content=self._content)
    async def embed(self, texts):  # pragma: no cover
        return [[0.0] for _ in texts]


def _listing(lid):
    now = datetime.now(UTC)
    listing = Listing(id=lid, source_id="otodom", external_id=str(lid), url="u",
                      title=f"oferta {lid}", raw_hash="h", status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[])
    return listing


async def test_parse_nl_query_filters_to_allowed_keys():
    client = _Client('{"max_price": 500000, "min_rooms": 2, "nonsense": 1}')
    out = await parse_nl_query(client, "tanie 2 pokoje")
    assert out == {"max_price": 500000, "min_rooms": 2}


async def test_parse_nl_query_bad_json_returns_empty():
    client = _Client("to nie json")
    assert await parse_nl_query(client, "x") == {}


async def test_match_and_rank_orders_and_filters():
    client = _Client('{"matches": [{"listing_id": 1, "score": 40, "reason": "ok"}, '
                     '{"listing_id": 2, "score": 95, "reason": "super"}, '
                     '{"listing_id": 999, "score": 80, "reason": "obcy"}]}')
    cands = [_listing(1), _listing(2)]
    out = await match_and_rank(client, cands, "blisko morza")
    assert [m.listing_id for m in out] == [2, 1]  # malejąco po score, 999 odfiltrowany
    assert all(isinstance(m, RankedMatch) for m in out)
    assert out[0].score == 95


async def test_match_and_rank_bad_json_returns_empty():
    client = _Client("nie json")
    assert await match_and_rank(client, [_listing(1)], "x") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/search/test_llm_search.py -v`
Expected: FAIL — brak modułu.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/search/llm_search.py
from __future__ import annotations

import json

from pydantic import BaseModel

from realestate.llm.base import ChatMessage, LLMClient
from realestate.models.listing import Listing

_ALLOWED_KEYS = {
    "max_price", "min_price", "min_rooms", "max_rooms",
    "min_area", "max_area", "districts", "market", "city",
}


class RankedMatch(BaseModel):
    listing_id: int
    score: float
    reason: str


def _safe_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


async def parse_nl_query(client: LLMClient, text: str) -> dict:
    messages = [
        ChatMessage(role="system", content=(
            "Zamień opis preferencji mieszkania na filtry. Zwróć WYŁĄCZNIE JSON o kluczach "
            "spośród: max_price, min_price, min_rooms, max_rooms, min_area, max_area, "
            "districts (lista), market, city. Pomiń nieznane."
        )),
        ChatMessage(role="user", content=text),
    ]
    result = await client.complete(messages, response_format={"type": "json_object"})
    data = _safe_json(result.content)
    return {k: v for k, v in data.items() if k in _ALLOWED_KEYS}


async def match_and_rank(
    client: LLMClient, candidates: list[Listing], nl_preferences: str
) -> list[RankedMatch]:
    valid_ids = {c.id for c in candidates}
    lines = [
        f"id={c.id} | {c.title} | cena={c.price if c.price is not None else '-'} | "
        f"{c.district or c.city or '-'} | {c.area_m2 or '-'} m2"
        for c in candidates
    ]
    messages = [
        ChatMessage(role="system", content=(
            "Oceń dopasowanie ofert do preferencji. Zwróć WYŁĄCZNIE JSON: "
            '{"matches":[{"listing_id":int,"score":0-100,"reason":str}]}.'
        )),
        ChatMessage(role="user", content=f"Preferencje: {nl_preferences}\n\n" + "\n".join(lines)),
    ]
    result = await client.complete(messages, response_format={"type": "json_object"})
    data = _safe_json(result.content)
    raw = data.get("matches") or []
    matches: list[RankedMatch] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            lid = item.get("listing_id")
            if lid not in valid_ids:
                continue
            try:
                score = max(0.0, min(100.0, float(item.get("score", 0))))
            except (TypeError, ValueError):
                score = 0.0
            matches.append(RankedMatch(listing_id=lid, score=score,
                                       reason=str(item.get("reason", ""))))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/search/test_llm_search.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/search/llm_search.py tests/search/test_llm_search.py
git commit -m "feat: funkcje LLM wyszukiwania — parse_nl_query + match_and_rank"
```

---

### Task 4: Wyszukiwanie hybrydowe w `SearchService` (pgvector top-K → rerank LLM, degradacja)

**Files:**
- Modify: `src/realestate/search/service.py`
- Test: `tests/search/test_hybrid_search.py`

**Interfaces:**
- Consumes: `match_and_rank`, `parse_nl_query` (Task 3), `LLMClient`, pgvector `cosine_distance`.
- Produces (rozszerzenie `SearchService`):
  - `async def search_hybrid(self, filters: ListingFilters, *, limit: int = 50, offset: int = 0, top_k: int = 50) -> tuple[list[RankedListing], int]`:
    - Jeśli `self.client is None` LUB brak `filters.nl_query` → deleguj do `self.search(filters, limit=limit, offset=offset)` (degradacja regułowa).
    - W przeciwnym razie:
      1. embed zapytania: `qvec = (await self.client.embed([filters.nl_query]))[0]`.
      2. kandydaci: te same twarde filtry + `Listing.embedding IS NOT NULL`, sortowane po `Listing.embedding.cosine_distance(qvec)` rosnąco, `limit top_k`. `total` = liczba pasujących twardych filtrów (jak w `search`).
      3. rerank: `matches = await match_and_rank(self.client, candidates, filters.nl_query)`.
      4. zbuduj wynik: dla każdego `RankedMatch` (w kolejności) dołącz odpowiedni `Listing` z `score`/`reason`; kandydatów bez dopasowania (LLM ich nie zwrócił) dołącz na końcu z `score=None`. Zastosuj `limit/offset` na finalnej liście.
    - Zwróć `(items, total)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_hybrid_search.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.config import get_embedding_dim
from realestate.llm.base import ChatMessage, LLMResult
from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService


class _HybridClient:
    """embed zwraca wektor zależny od 'mark'; complete zwraca ranking faworyzujący id2."""
    def __init__(self, matches_json):
        self._matches = matches_json
    async def embed(self, texts):
        dim = get_embedding_dim()
        return [[1.0] + [0.0] * (dim - 1) for _ in texts]
    async def complete(self, messages: list[ChatMessage], *, response_format=None) -> LLMResult:
        return LLMResult(content=self._matches)


async def _listing(s, *, ext, vec):
    now = datetime.now(UTC)
    listing = Listing(source_id="otodom", external_id=ext, url="u", title=f"o {ext}",
                      price=Decimal(400000), price_per_m2=Decimal(8000), area_m2=50.0,
                      rooms=2, district="Wrzeszcz", city="Gdansk",
                      raw_hash="h" + ext, status=ListingStatus.ACTIVE,
                      first_seen=now, last_seen=now, images=[], embedding=vec)
    s.add(listing)
    await s.flush()
    return listing


async def test_hybrid_degrades_to_rule_based_without_client(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        dim = get_embedding_dim()
        await _listing(s, ext="a", vec=[0.0] * dim)
        svc = SearchService(s, client=None)
        items, total = await svc.search_hybrid(ListingFilters(nl_query="cokolwiek"))
        assert total == 1 and items[0].score is None  # degradacja


async def test_hybrid_uses_llm_rerank(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        dim = get_embedding_dim()
        l1 = await _listing(s, ext="one", vec=[1.0] + [0.0] * (dim - 1))
        l2 = await _listing(s, ext="two", vec=[0.9] + [0.0] * (dim - 1))
        matches = ('{"matches": [{"listing_id": %d, "score": 90, "reason": "blisko"}, '
                   '{"listing_id": %d, "score": 30, "reason": "dalej"}]}' % (l2.id, l1.id))
        svc = SearchService(s, client=_HybridClient(matches))
        items, total = await svc.search_hybrid(ListingFilters(nl_query="blisko morza"))
        assert total == 2
        # ranking wg LLM: l2 (90) przed l1 (30)
        assert items[0].listing.id == l2.id and items[0].score == 90
        assert items[0].reason == "blisko"
        assert items[1].listing.id == l1.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/search/test_hybrid_search.py -v`
Expected: FAIL — brak `search_hybrid`.

- [ ] **Step 3: Write minimal implementation**

Dodaj do `SearchService` w `src/realestate/search/service.py` (zachowaj istniejący `search`). Dodaj importy: `from realestate.search.llm_search import match_and_rank`.

```python
    async def search_hybrid(
        self,
        filters: ListingFilters,
        *,
        limit: int = 50,
        offset: int = 0,
        top_k: int = 50,
    ) -> tuple[list["RankedListing"], int]:
        if self.client is None or not filters.nl_query:
            return await self.search(filters, limit=limit, offset=offset)

        qvec = (await self.client.embed([filters.nl_query]))[0]
        base = apply_filters(
            select(Listing).where(Listing.status == ListingStatus.ACTIVE), filters
        )
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        cand_stmt = (
            base.where(Listing.embedding.isnot(None))
            .order_by(Listing.embedding.cosine_distance(qvec))
            .limit(top_k)
        )
        candidates = list((await self.session.execute(cand_stmt)).scalars().all())

        matches = await match_and_rank(self.client, candidates, filters.nl_query)
        by_id = {c.id: c for c in candidates}
        ranked: list[RankedListing] = []
        used: set[int] = set()
        for m in matches:
            listing = by_id.get(m.listing_id)
            if listing is None:
                continue
            ranked.append(RankedListing(listing=listing, score=m.score, reason=m.reason))
            used.add(m.listing_id)
        for c in candidates:
            if c.id not in used:
                ranked.append(RankedListing(listing=c, score=None, reason=None))

        return ranked[offset : offset + limit], total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/search/test_hybrid_search.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/search/service.py tests/search/test_hybrid_search.py
git commit -m "feat: wyszukiwanie hybrydowe (pgvector top-K + rerank LLM, degradacja)"
```

---

### Task 5: Fundament API (DI) + schematy + `GET /listings` + `GET /listings/{id}`

**Files:**
- Modify: `src/realestate/api/app.py`
- Create: `src/realestate/api/deps.py`
- Create: `src/realestate/api/schemas.py`
- Create: `src/realestate/api/routes_listings.py`
- Test: `tests/api/test_listings_api.py`

**Interfaces:**
- Consumes: `create_engine`, `create_session_factory`, `get_llm_client`, `SearchService`, `ListingFilters`, repos, `Listing`, `LLMAnalysis`, `DedupMember`, `PriceHistory`.
- Produces:
  - `deps.py`: `get_session_factory(request) -> async_sessionmaker` (z `request.app.state.session_factory`); async dependency `get_session(request)` yielduje `AsyncSession`; `get_llm_client_dep()` (zwraca `get_llm_client()` — nadpisywalne w testach). 
  - `app.py`: w `create_app()` zbuduj `engine = create_engine(settings.database_url)`; `app.state.engine = engine`; `app.state.session_factory = create_session_factory(engine)`; dołącz routery; zachowaj `/health`. Dodaj `@app.on_event` lub lifespan do `engine.dispose()` przy zamknięciu (użyj `lifespan` async contextmanager — czysto).
  - `schemas.py`: `ListingOut` (id, source_id, external_id, url, title, price, price_per_m2, area_m2, rooms, floor, total_floors, city, district, street, market, images, posted_at, status, score, reason) — `from_listing(listing, *, score=None, reason=None)` classmethod; `PriceHistoryOut` (price, observed_at); `ListingDetailOut` (pola jak ListingOut + `price_history: list[PriceHistoryOut]` + `summary: str|None` + `features: dict|None` + `duplicate_listing_ids: list[int]`); `ListingsResponse` (`items: list[ListingOut]`, `total: int`). Użyj `ConfigDict` z `from_attributes=True` gdzie wygodnie; `Decimal`/`datetime` serializują się natywnie w FastAPI.
  - `routes_listings.py`: `router = APIRouter()`.
    - `GET /listings` — query params: city, district (wielokrotne → list), min_price, max_price, min_area, max_area, min_rooms, max_rooms, market, q (nl_query), limit=50, offset=0. Buduje `ListingFilters`, tworzy `SearchService(session, client=get_llm_client_dep())`, woła `search_hybrid`, zwraca `ListingsResponse`.
    - `GET /listings/{listing_id}` — pobiera `Listing`; 404 gdy brak; dokłada `price_history` (sort observed_at), najnowszą `LLMAnalysis` (summary/features) jeśli jest, oraz `duplicate_listing_ids` (inne listing_id w tej samej grupie dedup). Zwraca `ListingDetailOut`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_listings_api.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import get_llm_client_dep, get_session
from realestate.db.engine import create_session_factory
from realestate.models import Base, Listing, LLMAnalysis, PriceHistory
from realestate.models.enums import ListingStatus


async def _seed(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        listing = Listing(source_id="otodom", external_id="x1", url="http://x", title="Ładne 2pok",
                          price=Decimal(400000), price_per_m2=Decimal(8000), area_m2=50.0, rooms=2,
                          city="Gdansk", district="Wrzeszcz", raw_hash="h1",
                          status=ListingStatus.ACTIVE, first_seen=now, last_seen=now, images=[])
        s.add(listing)
        await s.flush()
        s.add(PriceHistory(listing_id=listing.id, price=Decimal(410000), observed_at=now))
        s.add(LLMAnalysis(listing_id=listing.id, content_hash="h1", summary="świetne",
                          features={"balkon": True}, model="m", created_at=now))
        await s.commit()
        return listing.id


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_llm_client_dep] = lambda: None  # degradacja
    return app


async def test_list_listings_with_filter(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/listings", params={"max_price": 500000, "min_rooms": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "x1"
    assert body["items"][0]["title"] == "Ładne 2pok"


async def test_listing_detail(engine):
    listing_id = await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get(f"/listings/{listing_id}")
        missing = await client.get("/listings/999999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "świetne"
    assert body["features"] == {"balkon": True}
    assert len(body["price_history"]) == 1
    assert missing.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_listings_api.py -v`
Expected: FAIL — brak `deps`/routerów.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/api/deps.py
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from realestate.llm.base import LLMClient
from realestate.llm.factory import get_llm_client


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(request)
    async with factory() as session:
        yield session


def get_llm_client_dep() -> LLMClient | None:
    return get_llm_client()
```

```python
# src/realestate/api/schemas.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from realestate.models.listing import Listing


class ListingOut(BaseModel):
    id: int
    source_id: str
    external_id: str
    url: str
    title: str
    price: Decimal | None = None
    price_per_m2: Decimal | None = None
    area_m2: float | None = None
    rooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    market: str | None = None
    images: list[str] = []
    posted_at: datetime | None = None
    status: str
    score: float | None = None
    reason: str | None = None

    @classmethod
    def from_listing(cls, listing: Listing, *, score=None, reason=None) -> "ListingOut":
        return cls(
            id=listing.id, source_id=listing.source_id, external_id=listing.external_id,
            url=listing.url, title=listing.title, price=listing.price,
            price_per_m2=listing.price_per_m2, area_m2=listing.area_m2, rooms=listing.rooms,
            floor=listing.floor, total_floors=listing.total_floors, city=listing.city,
            district=listing.district, street=listing.street,
            market=listing.market.value if listing.market else None,
            images=list(listing.images or []), posted_at=listing.posted_at,
            status=listing.status.value, score=score, reason=reason,
        )


class PriceHistoryOut(BaseModel):
    price: Decimal
    observed_at: datetime


class ListingDetailOut(ListingOut):
    price_history: list[PriceHistoryOut] = []
    summary: str | None = None
    features: dict | None = None
    duplicate_listing_ids: list[int] = []


class ListingsResponse(BaseModel):
    items: list[ListingOut]
    total: int
```

```python
# src/realestate/api/routes_listings.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_llm_client_dep, get_session
from realestate.api.schemas import (
    ListingDetailOut,
    ListingOut,
    ListingsResponse,
    PriceHistoryOut,
)
from realestate.models.dedup import DedupMember
from realestate.models.listing import Listing, PriceHistory
from realestate.models.llm_analysis import LLMAnalysis
from realestate.search.filters import ListingFilters
from realestate.search.service import SearchService

router = APIRouter()


@router.get("/listings", response_model=ListingsResponse)
async def list_listings(
    session: AsyncSession = Depends(get_session),
    client=Depends(get_llm_client_dep),
    city: str | None = None,
    district: list[str] | None = Query(default=None),
    min_price: int | None = None,
    max_price: int | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    market: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ListingsResponse:
    filters = ListingFilters(
        city=city, districts=district, min_price=min_price, max_price=max_price,
        min_area=min_area, max_area=max_area, min_rooms=min_rooms, max_rooms=max_rooms,
        market=market, nl_query=q,
    )
    svc = SearchService(session, client=client)
    items, total = await svc.search_hybrid(filters, limit=limit, offset=offset)
    return ListingsResponse(
        items=[ListingOut.from_listing(r.listing, score=r.score, reason=r.reason) for r in items],
        total=total,
    )


@router.get("/listings/{listing_id}", response_model=ListingDetailOut)
async def get_listing(
    listing_id: int, session: AsyncSession = Depends(get_session)
) -> ListingDetailOut:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

    history = (await session.execute(
        select(PriceHistory).where(PriceHistory.listing_id == listing_id)
        .order_by(PriceHistory.observed_at)
    )).scalars().all()

    analysis = (await session.execute(
        select(LLMAnalysis).where(LLMAnalysis.listing_id == listing_id)
        .order_by(LLMAnalysis.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    dup_ids: list[int] = []
    member = (await session.execute(
        select(DedupMember).where(DedupMember.listing_id == listing_id)
    )).scalar_one_or_none()
    if member is not None:
        rows = (await session.execute(
            select(DedupMember.listing_id).where(
                DedupMember.group_id == member.group_id,
                DedupMember.listing_id != listing_id,
            )
        )).scalars().all()
        dup_ids = list(rows)

    base = ListingOut.from_listing(listing)
    return ListingDetailOut(
        **base.model_dump(),
        price_history=[PriceHistoryOut(price=h.price, observed_at=h.observed_at) for h in history],
        summary=analysis.summary if analysis else None,
        features=analysis.features if analysis else None,
        duplicate_listing_ids=dup_ids,
    )
```

W `src/realestate/api/app.py` zmodyfikuj `create_app()`. **WAŻNE:** silnik bazy budujemy w `lifespan` (startup), a NIE w ciele `create_app()`. Dzięki temu `create_app()` nie wymaga `DATABASE_URL` przy konstrukcji — istniejący `tests/api/test_health.py` woła `create_app()` bez ustawiania `DATABASE_URL`, a testy API używają `ASGITransport`, który NIE uruchamia zdarzeń `lifespan`; testy i tak nadpisują `get_session`/`get_session_factory`, więc `app.state.session_factory` nie jest w nich potrzebny. Przy realnym uruchomieniu (`uvicorn`) `lifespan` zbuduje silnik na starcie.

```python
from contextlib import asynccontextmanager

from realestate.api.routes_listings import router as listings_router
from realestate.db.engine import create_engine, create_session_factory


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: zbuduj silnik z konfiguracji (wymaga DATABASE_URL w realnym uruchomieniu).
        engine = create_engine(get_settings().database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Agregator nieruchomości", lifespan=lifespan)

    @app.get("/health")
    async def health(db_ok: bool = Depends(get_db_health)) -> JSONResponse:
        ...  # bez zmian

    app.include_router(listings_router)
    return app
```
Uwaga dot. `get_session_factory` (z `deps.py`): czyta `request.app.state.session_factory`. W realnym uruchomieniu ustawia go `lifespan`. W testach endpointów `/scrape` (Task 6) nadpisuje się `get_session_factory` przez `dependency_overrides`, więc brak `app.state.session_factory` w testach nie jest problemem. NIE wołaj `get_settings()` w ciele `create_app()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_listings_api.py -v`
Expected: PASS. (Jeśli `create_app()` zgłosi brak `DATABASE_URL`, dodaj `monkeypatch.setenv` jak wyżej w `_app`/teście.)

- [ ] **Step 5: Commit**

```bash
git add src/realestate/api/ tests/api/test_listings_api.py
git commit -m "feat: API — DI + schematy + GET /listings + GET /listings/{id}"
```

---

### Task 6: Endpointy scrapingu — `POST /scrape`, `GET /scrape/runs`, `GET /scrape/runs/{id}`

**Files:**
- Modify: `src/realestate/repositories/scrape_runs.py` (dodaj `list_recent`, `get`)
- Create: `src/realestate/api/routes_scrape.py`
- Modify: `src/realestate/api/app.py` (include router), `src/realestate/api/deps.py` (fetcher dep)
- Modify: `src/realestate/api/schemas.py` (schematy ScrapeRun)
- Test: `tests/api/test_scrape_api.py`

**Interfaces:**
- Consumes: `IngestionService`, `ScrapeRunRepository`, `SearchCriteria`, `BrowserFetcher`, `get_session_factory`.
- Produces:
  - `ScrapeRunRepository.list_recent(limit=50) -> list[ScrapeRun]` (order by started_at desc); `ScrapeRunRepository.get(run_id) -> ScrapeRun | None` (`session.get`).
  - `deps.py`: `get_fetcher_dep()` → zwraca `BrowserFetcher()` (nadpisywane w testach fake'iem). 
  - `schemas.py`: `ScrapeRunOut` (id, source_id, started_at, finished_at, status, new_count, updated_count, gone_count, unchanged_count, error_message); `ScrapeRequest` (`city: str`, opcjonalne pola filtrów scrapera: min_price/max_price/min_area/max_area/min_rooms/max_rooms/market, `source_ids: list[str]|None=None`, `max_pages: int=1`); `ScrapeResponse` (`runs: list[ScrapeRunOut]`).
  - `routes_scrape.py`:
    - `POST /scrape` (body `ScrapeRequest`): buduje `SearchCriteria`, tworzy `IngestionService(session_factory, fetcher)` (fetcher z `get_fetcher_dep`), woła `ingest(...)`, zwraca `ScrapeResponse`. Uwaga: `IngestionService` zarządza własnymi sesjami przez `session_factory` (z `get_session_factory(request)`), więc ten endpoint NIE używa `get_session`.
    - `GET /scrape/runs` (query `limit=50`): lista przez `ScrapeRunRepository` w sesji z `get_session`.
    - `GET /scrape/runs/{run_id}`: 404 gdy brak.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_scrape_api.py
import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_fetcher_dep, get_session, get_session_factory
from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.scrapers.base import _REGISTRY
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True
    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        return '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}</script></html>'


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401
    saved = dict(base._REGISTRY)
    keep = {"otodom": base._REGISTRY["otodom"]}
    base._REGISTRY.clear()
    base._REGISTRY.update(keep)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def _create_schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    return app


async def test_scrape_then_list_runs(engine):
    await _create_schema(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/scrape", json={"city": "gdansk", "source_ids": ["otodom"],
                                                   "max_pages": 2})
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["new_count"] >= 20
        run_id = runs[0]["id"]

        listed = await client.get("/scrape/runs")
        assert listed.status_code == 200
        assert any(r["id"] == run_id for r in listed.json())

        one = await client.get(f"/scrape/runs/{run_id}")
        assert one.status_code == 200 and one.json()["id"] == run_id

        missing = await client.get("/scrape/runs/999999")
        assert missing.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_scrape_api.py -v`
Expected: FAIL — brak endpointów/zależności.

- [ ] **Step 3: Write minimal implementation**

W `src/realestate/repositories/scrape_runs.py` dodaj:
```python
    async def list_recent(self, limit: int = 50) -> list[ScrapeRun]:
        stmt = select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, run_id: int) -> ScrapeRun | None:
        return await self.session.get(ScrapeRun, run_id)
```

W `src/realestate/api/deps.py` dodaj:
```python
def get_fetcher_dep():
    from realestate.scrapers.browser import BrowserFetcher
    return BrowserFetcher()
```

W `src/realestate/api/schemas.py` dodaj:
```python
class ScrapeRunOut(BaseModel):
    id: int
    source_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    new_count: int
    updated_count: int
    gone_count: int
    unchanged_count: int
    error_message: str | None = None

    @classmethod
    def from_run(cls, run) -> "ScrapeRunOut":
        return cls(
            id=run.id, source_id=run.source_id, started_at=run.started_at,
            finished_at=run.finished_at, status=run.status.value,
            new_count=run.new_count, updated_count=run.updated_count,
            gone_count=run.gone_count, unchanged_count=run.unchanged_count,
            error_message=run.error_message,
        )


class ScrapeRequest(BaseModel):
    city: str
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    market: str | None = None
    source_ids: list[str] | None = None
    max_pages: int = 1


class ScrapeResponse(BaseModel):
    runs: list[ScrapeRunOut]
```

```python
# src/realestate/api/routes_scrape.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_fetcher_dep, get_session, get_session_factory
from realestate.api.schemas import ScrapeRequest, ScrapeResponse, ScrapeRunOut
from realestate.ingestion.service import IngestionService
from realestate.repositories.scrape_runs import ScrapeRunRepository
from realestate.scrapers.base import SearchCriteria

router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    body: ScrapeRequest,
    session_factory=Depends(get_session_factory),
    fetcher=Depends(get_fetcher_dep),
) -> ScrapeResponse:
    criteria = SearchCriteria(
        city=body.city, min_price=body.min_price, max_price=body.max_price,
        min_area=body.min_area, max_area=body.max_area, min_rooms=body.min_rooms,
        max_rooms=body.max_rooms, market=body.market,
    )
    service = IngestionService(session_factory, fetcher)
    runs = await service.ingest(criteria, source_ids=body.source_ids, max_pages=body.max_pages)
    return ScrapeResponse(runs=[ScrapeRunOut.from_run(r) for r in runs])


@router.get("/scrape/runs", response_model=list[ScrapeRunOut])
async def list_runs(
    limit: int = 50, session: AsyncSession = Depends(get_session)
) -> list[ScrapeRunOut]:
    runs = await ScrapeRunRepository(session).list_recent(limit=limit)
    return [ScrapeRunOut.from_run(r) for r in runs]


@router.get("/scrape/runs/{run_id}", response_model=ScrapeRunOut)
async def get_run(run_id: int, session: AsyncSession = Depends(get_session)) -> ScrapeRunOut:
    run = await ScrapeRunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return ScrapeRunOut.from_run(run)
```

W `app.py` dołącz `routes_scrape.router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_scrape_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/realestate/repositories/scrape_runs.py src/realestate/api/ tests/api/test_scrape_api.py
git commit -m "feat: API scrapingu — POST /scrape + GET /scrape/runs[/{id}]"
```

---

### Task 7: Endpointy `searches`, `favorites`, `settings`

**Files:**
- Create: `src/realestate/api/routes_user.py`
- Modify: `src/realestate/api/app.py` (include router), `src/realestate/api/schemas.py`
- Test: `tests/api/test_user_api.py`

**Interfaces:**
- Consumes: `SavedSearchRepository`, `FavoriteRepository`, `AppSettingRepository`, `Source`, `get_settings`, `get_scrapers`.
- Produces:
  - `schemas.py`: `SavedSearchIn` (`name: str`, `filters: dict = {}`, `nl_query: str|None=None`); `SavedSearchOut` (id, name, filters, nl_query, created_at); `FavoriteIn` (`listing_id: int`); `FavoriteOut` (id, listing_id, created_at); `SettingsOut` (`llm_enabled: bool`, `llm_base_url: str`, `llm_model: str|None`, `llm_embedding_model: str|None`, `llm_api_key_set: bool`, `scheduler_interval_minutes: int|None`, `sources: list[str]`); `SettingsUpdate` (`scheduler_interval_minutes: int|None=None`, `enabled_source_ids: list[str]|None=None`).
  - `routes_user.py`:
    - `GET /searches`, `POST /searches` (body `SavedSearchIn`), `DELETE /searches/{id}` (404 gdy brak).
    - `GET /favorites`, `POST /favorites` (body `FavoriteIn`, idempotentne), `DELETE /favorites/{listing_id}` (404 gdy nie było).
    - `GET /settings` — NIGDY nie zwraca `llm_api_key`; zwraca `llm_api_key_set = bool(settings.llm_api_key)`, model/base_url/embedding_model z `Settings`, `scheduler_interval_minutes` z `AppSettingRepository.get("scheduler_interval_minutes")` (klucz `{"v": int}` → `v`, brak → `None`), `sources` = `list(get_scrapers().keys())`.
    - `PUT /settings` (body `SettingsUpdate`) — zapisuje do `app_settings`: `scheduler_interval_minutes` jako `{"v": n}` (gdy podane), `enabled_source_ids` jako `{"v": [...]}` (gdy podane); zwraca zaktualizowane `SettingsOut`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_user_api.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.app import create_app
from realestate.api.deps import get_llm_client_dep, get_session
from realestate.db.engine import create_session_factory
from realestate.models import Base, Listing
from realestate.models.enums import ListingStatus


async def _seed(engine) -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        now = datetime.now(UTC)
        listing = Listing(source_id="otodom", external_id="x1", url="u", title="t",
                          price=Decimal(1), raw_hash="h", status=ListingStatus.ACTIVE,
                          first_seen=now, last_seen=now, images=[])
        s.add(listing)
        await s.commit()
        return listing.id


def _app(engine):
    app = create_app()
    factory = create_session_factory(engine)

    async def _override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_llm_client_dep] = lambda: None
    return app


async def test_saved_searches_crud(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        created = await client.post("/searches", json={"name": "tanie",
                                                        "filters": {"max_price": 500000},
                                                        "nl_query": "blisko morza"})
        assert created.status_code == 201
        sid = created.json()["id"]
        listed = await client.get("/searches")
        assert any(x["id"] == sid for x in listed.json())
        deleted = await client.delete(f"/searches/{sid}")
        assert deleted.status_code == 204
        # ponowne usunięcie nieistniejącego → 404
        assert (await client.delete(f"/searches/{sid}")).status_code == 404


async def test_favorites_idempotent(engine):
    listing_id = await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r1 = await client.post("/favorites", json={"listing_id": listing_id})
        r2 = await client.post("/favorites", json={"listing_id": listing_id})
        assert r1.status_code == 201 and r2.status_code == 201
        listed = await client.get("/favorites")
        assert len(listed.json()) == 1
        d = await client.delete(f"/favorites/{listing_id}")
        assert d.status_code == 204
        assert (await client.delete(f"/favorites/{listing_id}")).status_code == 404


async def test_settings_get_and_put_masks_secret(engine):
    await _seed(engine)
    app = _app(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        got = await client.get("/settings")
        assert got.status_code == 200
        body = got.json()
        assert "llm_api_key" not in body
        assert "llm_api_key_set" in body
        assert body["scheduler_interval_minutes"] is None
        put = await client.put("/settings", json={"scheduler_interval_minutes": 30})
        assert put.status_code == 200
        assert put.json()["scheduler_interval_minutes"] == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_user_api.py -v`
Expected: FAIL — brak routera user.

- [ ] **Step 3: Write minimal implementation**

W `schemas.py` dodaj `SavedSearchIn/Out`, `FavoriteIn/Out`, `SettingsOut`, `SettingsUpdate` (pola jak w Interfaces; `created_at: datetime`).

```python
# src/realestate/api/routes_user.py
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.api.deps import get_session
from realestate.api.schemas import (
    FavoriteIn,
    FavoriteOut,
    SavedSearchIn,
    SavedSearchOut,
    SettingsOut,
    SettingsUpdate,
)
from realestate.config import get_settings
from realestate.models.user_data import SavedSearch
from realestate.repositories.user_data import (
    AppSettingRepository,
    FavoriteRepository,
    SavedSearchRepository,
)
from realestate.scrapers.base import get_scrapers

router = APIRouter()


@router.get("/searches", response_model=list[SavedSearchOut])
async def list_searches(session: AsyncSession = Depends(get_session)):
    rows = await SavedSearchRepository(session).list_all()
    return [SavedSearchOut(id=r.id, name=r.name, filters=r.filters, nl_query=r.nl_query,
                           created_at=r.created_at) for r in rows]


@router.post("/searches", response_model=SavedSearchOut, status_code=201)
async def create_search(body: SavedSearchIn, session: AsyncSession = Depends(get_session)):
    repo = SavedSearchRepository(session)
    created = await repo.add(SavedSearch(name=body.name, filters=body.filters,
                                         nl_query=body.nl_query, created_at=datetime.now(UTC)))
    await session.commit()
    return SavedSearchOut(id=created.id, name=created.name, filters=created.filters,
                          nl_query=created.nl_query, created_at=created.created_at)


@router.delete("/searches/{search_id}", status_code=204)
async def delete_search(search_id: int, session: AsyncSession = Depends(get_session)):
    ok = await SavedSearchRepository(session).delete(search_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="search not found")
    return Response(status_code=204)


@router.get("/favorites", response_model=list[FavoriteOut])
async def list_favorites(session: AsyncSession = Depends(get_session)):
    rows = await FavoriteRepository(session).list_all()
    return [FavoriteOut(id=r.id, listing_id=r.listing_id, created_at=r.created_at) for r in rows]


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
async def add_favorite(body: FavoriteIn, session: AsyncSession = Depends(get_session)):
    fav = await FavoriteRepository(session).add(body.listing_id)
    await session.commit()
    return FavoriteOut(id=fav.id, listing_id=fav.listing_id, created_at=fav.created_at)


@router.delete("/favorites/{listing_id}", status_code=204)
async def delete_favorite(listing_id: int, session: AsyncSession = Depends(get_session)):
    ok = await FavoriteRepository(session).delete(listing_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="favorite not found")
    return Response(status_code=204)


async def _build_settings_out(session: AsyncSession) -> SettingsOut:
    settings = get_settings()
    app_repo = AppSettingRepository(session)
    interval = await app_repo.get("scheduler_interval_minutes")
    return SettingsOut(
        llm_enabled=settings.llm_enabled,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_embedding_model=settings.llm_embedding_model,
        llm_api_key_set=bool(settings.llm_api_key),
        scheduler_interval_minutes=interval["v"] if interval else None,
        sources=list(get_scrapers().keys()),
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings_endpoint(session: AsyncSession = Depends(get_session)):
    return await _build_settings_out(session)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsUpdate, session: AsyncSession = Depends(get_session)):
    app_repo = AppSettingRepository(session)
    if body.scheduler_interval_minutes is not None:
        await app_repo.set("scheduler_interval_minutes", {"v": body.scheduler_interval_minutes})
    if body.enabled_source_ids is not None:
        await app_repo.set("enabled_source_ids", {"v": body.enabled_source_ids})
    await session.commit()
    return await _build_settings_out(session)
```

W `app.py` dołącz `routes_user.router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_user_api.py -v`
Expected: PASS.

- [ ] **Step 5: Pełny zestaw + lint**

Run: `uv run pytest && uv run ruff check .`
Expected: wszystko zielone, ruff czysty.

- [ ] **Step 6: Commit**

```bash
git add src/realestate/api/ tests/api/test_user_api.py
git commit -m "feat: API — searches, favorites, settings (maskowanie sekretu)"
```

---

## Definicja ukończenia (Plan 5)
- `uv run pytest` zielony; `uv run ruff check .` bez błędów; jedna głowa migracji (`0007`).
- `SearchService`: twarde filtry SQL + ranking regułowy; wyszukiwanie hybrydowe (pgvector top-K → rerank LLM) z degradacją do regułowego bez klienta lub bez `nl_query`.
- Funkcje LLM `parse_nl_query` + `match_and_rank` z bezpiecznym parsowaniem JSON.
- REST API: `GET /listings` (filtry + ranking + paginacja), `GET /listings/{id}` (historia cen + analiza LLM + duplikaty), `POST /scrape` + `GET /scrape/runs[/{id}]`, `GET/POST/DELETE /searches`, `GET/POST/DELETE /favorites`, `GET/PUT /settings` (bez ujawniania `llm_api_key`).
- Tabele `saved_searches`, `favorites`, `app_settings` (migracja 0007).
- Testy API na realnym kontenerze pg18 przez `ASGITransport` + `dependency_overrides`.
