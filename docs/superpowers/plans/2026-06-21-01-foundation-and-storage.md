# Fundament i magazyn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postawić szkielet projektu (Python/uv + FastAPI), uruchamialną bazę PostgreSQL+pgvector z migracjami i kanonicznym modelem danych oraz repozytorium ofert — gotowy, przetestowany fundament pod kolejne plany.

**Architecture:** Modularny monolit. Pakiet `src/realestate/` z warstwami: `config`, `db`, `models`, `repositories`, `api`. SQLAlchemy 2.0 (async, asyncpg) + Alembic do migracji, rozszerzenie `pgvector` dla kolumny embeddingów. FastAPI udostępnia healthcheck. Testy integracyjne bazy na realnym Postgresie w kontenerze (testcontainers).

**Tech Stack:** Python 3.12, uv, FastAPI, Uvicorn, SQLAlchemy 2.0 (asyncio), asyncpg, Alembic, pgvector, Pydantic v2, pydantic-settings, pytest, pytest-asyncio, httpx, testcontainers[postgres], ruff. Docker Compose (obraz `pgvector/pgvector:pg16`).

## Global Constraints

- Python: **3.12**; zarządzanie zależnościami i uruchamianie przez **uv** (`uv run ...`).
- Brak hardcodowanych sekretów/konfiguracji — wszystko przez `pydantic-settings` (env / `.env`). `.env.example` jako wzór, `.env` w `.gitignore`.
- ORM: **SQLAlchemy 2.0** styl deklaratywny `Mapped[...]` / `mapped_column(...)`, w pełni **async** (`asyncpg`).
- Migracje schematu **wyłącznie przez Alembic** (żadnego `create_all` w kodzie produkcyjnym).
- Embeddingi: kolumna `pgvector` o wymiarze z konfiguracji (`EMBEDDING_DIM`, domyślnie 1536).
- TDD: każdy task = czerwony test → minimalna implementacja → zielony test → commit.
- Lint: `ruff` musi przechodzić przed commitem (`uv run ruff check .`).
- Testy bazodanowe używają realnego Postgresa+pgvector (testcontainers), nie SQLite.

---

### Task 1: Scaffolding projektu (uv, struktura, AGENTS.md, narzędzia)

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `AGENTS.md`
- Create: `CLAUDE.md` (symlink → `AGENTS.md`)
- Create: `src/realestate/__init__.py`
- Create: `README.md`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nic (pierwszy task).
- Produces: pakiet importowalny `realestate` (`realestate.__version__: str`); działające `uv run pytest` i `uv run ruff check .`.

- [ ] **Step 1: Napisz failujący test smoke**

`tests/test_smoke.py`:
```python
import realestate


def test_package_has_version():
    assert isinstance(realestate.__version__, str)
    assert realestate.__version__
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate'` (lub błąd braku konfiguracji projektu).

- [ ] **Step 3: Utwórz `pyproject.toml`**

```toml
[project]
name = "realestate-aggregator"
version = "0.1.0"
description = "Agregator ofert nieruchomości (Trójmiasto)"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0.29",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pgvector>=0.2.5",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "testcontainers[postgres]>=4.0",
    "ruff>=0.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/realestate"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 4: Utwórz pakiet i pliki pomocnicze**

`src/realestate/__init__.py`:
```python
__version__ = "0.1.0"
```

`.gitignore`:
```gitignore
__pycache__/
*.py[cod]
.venv/
.env
.pytest_cache/
.ruff_cache/
dist/
build/
node_modules/
*.egg-info/
```

`.env.example`:
```dotenv
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://realestate:realestate@localhost:5432/realestate

# Embeddingi
EMBEDDING_DIM=1536
```

`README.md`:
```markdown
# Agregator ofert nieruchomości (Trójmiasto)

Lokalna aplikacja agregująca oferty mieszkań z wielu portali. Patrz `docs/`.

## Szybki start (dev)

    uv sync --extra dev
    docker compose up -d db
    uv run pytest
```

`AGENTS.md`:
```markdown
# AGENTS.md

Instrukcje dla agentów/developerów pracujących w tym repozytorium.

## Stack
- Python 3.12, uv. Uruchamianie: `uv run <cmd>`.
- FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector.
- PostgreSQL+pgvector przez docker compose (`docker compose up -d db`).

## Zasady
- TDD: test → implementacja → commit.
- Lint: `uv run ruff check .` musi przechodzić.
- Brak sekretów w repo — konfiguracja przez `pydantic-settings` (`.env`).
- Migracje schematu tylko przez Alembic.

## Komendy
- Testy: `uv run pytest`
- Lint: `uv run ruff check .`
- Migracje: `uv run alembic upgrade head`
- App: `uv run uvicorn realestate.api.app:app --reload`

Specyfikacje: `docs/superpowers/specs/`. Plany: `docs/superpowers/plans/`.
```

- [ ] **Step 5: Utwórz symlink CLAUDE.md → AGENTS.md i zsynchronizuj zależności**

Run:
```bash
ln -s AGENTS.md CLAUDE.md
uv sync --extra dev
```
Expected: symlink utworzony; `uv` tworzy `.venv` i instaluje zależności.

- [ ] **Step 6: Uruchom test — ma przejść + lint**

Run: `uv run pytest tests/test_smoke.py -v && uv run ruff check .`
Expected: PASS; ruff bez błędów.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example AGENTS.md CLAUDE.md README.md src/realestate/__init__.py tests/test_smoke.py
git commit -m "chore: scaffolding projektu (uv, FastAPI stack, AGENTS.md)"
```

---

### Task 2: Konfiguracja aplikacji (pydantic-settings)

**Files:**
- Create: `src/realestate/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nic istotnego (czyta env).
- Produces:
  - `Settings` (pydantic-settings) z polami: `database_url: str`, `embedding_dim: int = 1536`.
  - `get_settings() -> Settings` — cache'owana (`functools.lru_cache`) fabryka.

- [ ] **Step 1: Napisz failujący test**

`tests/test_config.py`:
```python
from realestate.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("EMBEDDING_DIM", "768")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"
    assert settings.embedding_dim == 768


def test_embedding_dim_defaults_to_1536(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.delenv("EMBEDDING_DIM", raising=False)
    assert Settings().embedding_dim == 1536
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.config'`.

- [ ] **Step 3: Zaimplementuj `config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    embedding_dim: int = 1536


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (oba testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/config.py tests/test_config.py
git commit -m "feat: konfiguracja przez pydantic-settings"
```

---

### Task 3: Docker Compose (Postgres+pgvector) + warstwa połączenia DB

**Files:**
- Create: `docker-compose.yml`
- Create: `src/realestate/db/__init__.py`
- Create: `src/realestate/db/engine.py`
- Test: `tests/conftest.py`
- Test: `tests/db/test_engine.py`

**Interfaces:**
- Consumes: `realestate.config.Settings`.
- Produces:
  - `create_engine(database_url: str) -> AsyncEngine`
  - `create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`
  - Fixture pytest `pg_url` (sesyjny) — URL do Postgresa+pgvector w kontenerze (asyncpg DSN).
  - Fixture pytest `engine` — `AsyncEngine` na bazie `pg_url`.

- [ ] **Step 1: Utwórz `docker-compose.yml`**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: realestate
      POSTGRES_PASSWORD: realestate
      POSTGRES_DB: realestate
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U realestate"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

- [ ] **Step 2: Napisz fixture'y testowe (conftest) i failujący test**

`tests/conftest.py`:
```python
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from realestate.db.engine import create_engine


@pytest.fixture(scope="session")
def pg_url() -> str:
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        raw = pg.get_connection_url()  # postgresql+psycopg2://...
        yield raw.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url):
    eng = create_engine(pg_url)
    yield eng
    await eng.dispose()
```

`tests/db/test_engine.py`:
```python
from sqlalchemy import text


async def test_engine_connects(engine):
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
```

- [ ] **Step 3: Uruchom test — ma faliować**

Run: `uv run pytest tests/db/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.db.engine'`.

- [ ] **Step 4: Zaimplementuj `db/engine.py`**

`src/realestate/db/__init__.py`:
```python
```

`src/realestate/db/engine.py`:
```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 5: Uruchom test — ma przejść**

Run: `uv run pytest tests/db/test_engine.py -v`
Expected: PASS (testcontainers wystartuje kontener pgvector; pierwszy raz wolniej — pobranie obrazu).

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml src/realestate/db/ tests/conftest.py tests/db/test_engine.py
git commit -m "feat: docker-compose pgvector + warstwa połączenia DB (async)"
```

---

### Task 4: Baza deklaratywna + włączenie rozszerzenia pgvector (Alembic)

**Files:**
- Create: `src/realestate/models/__init__.py`
- Create: `src/realestate/models/base.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_enable_pgvector.py`
- Test: `tests/db/test_migrations.py`

**Interfaces:**
- Consumes: `realestate.db.engine.create_engine`, `realestate.config.get_settings`.
- Produces:
  - `Base` — deklaratywna baza (`DeclarativeBase`) z `metadata`.
  - Działające `alembic upgrade head`, które tworzy rozszerzenie `vector` w bazie.

- [ ] **Step 1: Utwórz bazę deklaratywną**

`src/realestate/models/__init__.py`:
```python
from realestate.models.base import Base

__all__ = ["Base"]
```

`src/realestate/models/base.py`:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Skonfiguruj Alembic (async)**

`alembic.ini` (kluczowe sekcje):
```ini
[alembic]
script_location = migrations
prepend_sys_path = src

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

`migrations/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`migrations/env.py`:
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from realestate.config import get_settings
from realestate.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Napisz failujący test migracji**

Na tym etapie katalog `migrations/versions/` jest pusty — `upgrade head` nic nie zrobi, więc rozszerzenie `vector` nie powstanie i test będzie czerwony.

`tests/db/test_migrations.py`:
```python
from alembic import command
from alembic.config import Config
from sqlalchemy import text


def _alembic_config(pg_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_url)
    return cfg


async def test_pgvector_extension_enabled(engine, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from realestate.config import get_settings
    get_settings.cache_clear()
    command.upgrade(_alembic_config(pg_url), "head")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        assert result.scalar_one_or_none() == 1
```

- [ ] **Step 4: Uruchom test — ma faliować**

Run: `uv run pytest tests/db/test_migrations.py -v`
Expected: FAIL — `assert None == 1` (brak migracji, rozszerzenie `vector` nieobecne).

- [ ] **Step 5: Utwórz migrację włączającą pgvector**

`migrations/versions/0001_enable_pgvector.py`:
```python
"""enable pgvector

Revision ID: 0001
Revises:
Create Date: 2026-06-21
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 6: Uruchom test — ma przejść**

Run: `uv run pytest tests/db/test_migrations.py -v`
Expected: PASS — rozszerzenie `vector` istnieje po `upgrade head`.

- [ ] **Step 7: Commit**

```bash
git add alembic.ini migrations/ src/realestate/models/ tests/db/test_migrations.py
git commit -m "feat: konfiguracja Alembic + migracja włączająca pgvector"
```

---

### Task 5: Model słownikowy `sources` + enumy domenowe

**Files:**
- Create: `src/realestate/models/enums.py`
- Create: `src/realestate/models/source.py`
- Modify: `src/realestate/models/__init__.py`
- Create: `migrations/versions/0002_sources.py`
- Test: `tests/db/test_source_model.py`

**Interfaces:**
- Consumes: `Base`.
- Produces:
  - `MarketType(str, Enum)` z wartościami `PRIMARY = "primary"`, `SECONDARY = "secondary"`.
  - `ListingStatus(str, Enum)` z wartościami `ACTIVE = "active"`, `GONE = "gone"`.
  - Model `Source`: `id: int (pk)`, `source_id: str (unique, np. "otodom")`, `display_name: str`, `enabled: bool = True`, `config: dict (JSONB, default {})`.

- [ ] **Step 1: Napisz failujący test**

`tests/db/test_source_model.py`:
```python
from sqlalchemy import select

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.source import Source


async def test_source_roundtrip(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(Source(source_id="otodom", display_name="Otodom"))
        await session.commit()
    async with factory() as session:
        row = (await session.execute(select(Source))).scalar_one()
        assert row.source_id == "otodom"
        assert row.enabled is True
        assert row.config == {}
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/db/test_source_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.models.source'`.

- [ ] **Step 3: Zaimplementuj enumy i model**

`src/realestate/models/enums.py`:
```python
from enum import Enum


class MarketType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    GONE = "gone"
```

`src/realestate/models/source.py`:
```python
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from realestate.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
```

`src/realestate/models/__init__.py`:
```python
from realestate.models.base import Base
from realestate.models.enums import ListingStatus, MarketType
from realestate.models.source import Source

__all__ = ["Base", "Source", "MarketType", "ListingStatus"]
```

- [ ] **Step 4: Utwórz migrację `0002_sources`**

`migrations/versions/0002_sources.py`:
```python
"""sources

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_sources_source_id", "sources", ["source_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sources_source_id", table_name="sources")
    op.drop_table("sources")
```

- [ ] **Step 5: Uruchom test — ma przejść**

Run: `uv run pytest tests/db/test_source_model.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/realestate/models/ migrations/versions/0002_sources.py tests/db/test_source_model.py
git commit -m "feat: model Source + enumy domenowe + migracja"
```

---

### Task 6: Model `Listing` (kanoniczna oferta + embedding pgvector) + `price_history`

**Files:**
- Create: `src/realestate/models/listing.py`
- Modify: `src/realestate/models/__init__.py`
- Create: `migrations/versions/0003_listings.py`
- Test: `tests/db/test_listing_model.py`

**Interfaces:**
- Consumes: `Base`, `MarketType`, `ListingStatus`, `get_settings().embedding_dim`.
- Produces:
  - Model `Listing` z polami: `id: int (pk)`, `source_id: str`, `external_id: str`,
    `url: str`, `title: str`, `price: Decimal | None`, `price_per_m2: Decimal | None`,
    `area_m2: float | None`, `rooms: int | None`, `floor: int | None`,
    `total_floors: int | None`, `city: str | None`, `district: str | None`,
    `street: str | None`, `lat: float | None`, `lon: float | None`,
    `market: MarketType | None`, `description: str | None`, `images: list[str]`,
    `posted_at: datetime | None`, `raw_hash: str`, `status: ListingStatus`,
    `first_seen: datetime`, `last_seen: datetime`, `embedding: Vector | None`.
    Unikalność `(source_id, external_id)`.
  - Model `PriceHistory`: `id`, `listing_id (fk)`, `price: Decimal`, `observed_at: datetime`.

- [ ] **Step 1: Napisz failujący test**

`tests/db/test_listing_model.py`:
```python
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing


async def _create_all(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _listing(**kw):
    now = datetime.now(timezone.utc)
    base = dict(
        source_id="otodom", external_id="abc", url="https://x/abc", title="Mieszkanie",
        price=Decimal("750000"), area_m2=52.0, rooms=3, market=MarketType.SECONDARY,
        images=["https://img/1.jpg"], raw_hash="h1", status=ListingStatus.ACTIVE,
        first_seen=now, last_seen=now,
    )
    base.update(kw)
    return Listing(**base)


async def test_listing_roundtrip(engine):
    await _create_all(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(_listing())
        await session.commit()
    async with factory() as session:
        row = (await session.execute(select(Listing))).scalar_one()
        assert row.external_id == "abc"
        assert row.market == MarketType.SECONDARY
        assert row.images == ["https://img/1.jpg"]


async def test_listing_unique_source_external(engine):
    await _create_all(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(_listing())
        session.add(_listing())  # ten sam (source_id, external_id)
        with pytest.raises(IntegrityError):
            await session.commit()
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/db/test_listing_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.models.listing'`.

- [ ] **Step 3: Zaimplementuj model**

`src/realestate/models/listing.py`:
```python
import os
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from realestate.models.base import Base
from realestate.models.enums import ListingStatus, MarketType

# Wymiar embeddingu czytany bezpośrednio z env, aby import modelu NIE wymagał
# pełnej konfiguracji (Settings wymaga DATABASE_URL). Jedno źródło wartości: EMBEDDING_DIM.
_EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    market: Mapped[MarketType | None] = mapped_column(SAEnum(MarketType), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(ListingStatus), default=ListingStatus.ACTIVE
    )
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)

    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    listing: Mapped[Listing] = relationship(back_populates="price_history")
```

`src/realestate/models/__init__.py`:
```python
from realestate.models.base import Base
from realestate.models.enums import ListingStatus, MarketType
from realestate.models.listing import Listing, PriceHistory
from realestate.models.source import Source

__all__ = [
    "Base",
    "Source",
    "Listing",
    "PriceHistory",
    "MarketType",
    "ListingStatus",
]
```

- [ ] **Step 4: Utwórz migrację `0003_listings`**

`migrations/versions/0003_listings.py`:
```python
"""listings + price_history

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""
import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

market = postgresql.ENUM("primary", "secondary", name="markettype")
status = postgresql.ENUM("active", "gone", name="listingstatus")


def upgrade() -> None:
    bind = op.get_bind()
    market.create(bind, checkfirst=True)
    status.create(bind, checkfirst=True)
    dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_per_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("district", sa.String(128), nullable=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("market", market, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("images", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("status", status, nullable=False, server_default="active"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=True),
        sa.UniqueConstraint("source_id", "external_id", name="uq_source_external"),
    )
    op.create_index("ix_listings_source_id", "listings", ["source_id"])
    op.create_index("ix_listings_district", "listings", ["district"])
    op.create_index("ix_listings_raw_hash", "listings", ["raw_hash"])
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "listing_id",
            sa.Integer(),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_index("ix_listings_raw_hash", table_name="listings")
    op.drop_index("ix_listings_district", table_name="listings")
    op.drop_index("ix_listings_source_id", table_name="listings")
    op.drop_table("listings")
    status.drop(op.get_bind(), checkfirst=True)
    market.drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 5: Uruchom test — ma przejść**

Run: `uv run pytest tests/db/test_listing_model.py -v`
Expected: PASS (oba testy).

- [ ] **Step 6: Commit**

```bash
git add src/realestate/models/ migrations/versions/0003_listings.py tests/db/test_listing_model.py
git commit -m "feat: model Listing (z embedding pgvector) + PriceHistory + migracja"
```

---

### Task 7: Repozytorium ofert (`ListingRepository`) — upsert + pobieranie

**Files:**
- Create: `src/realestate/repositories/__init__.py`
- Create: `src/realestate/repositories/listings.py`
- Test: `tests/repositories/test_listing_repository.py`

**Interfaces:**
- Consumes: `AsyncSession` (z `create_session_factory`), `Listing`.
- Produces:
  - `class ListingRepository(session: AsyncSession)`
  - `async get_by_external(source_id: str, external_id: str) -> Listing | None`
  - `async add(listing: Listing) -> Listing`
  - `async list_active(limit: int = 100, offset: int = 0) -> list[Listing]`
  - `async count_active() -> int`

- [ ] **Step 1: Napisz failujący test**

`tests/repositories/test_listing_repository.py`:
```python
from datetime import datetime, timezone
from decimal import Decimal

from realestate.db.engine import create_session_factory
from realestate.models import Base
from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing
from realestate.repositories.listings import ListingRepository


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_session_factory(engine)


def _listing(external_id="a", **kw):
    now = datetime.now(timezone.utc)
    base = dict(
        source_id="otodom", external_id=external_id, url="https://x", title="t",
        price=Decimal("500000"), raw_hash="h", status=ListingStatus.ACTIVE,
        images=[], first_seen=now, last_seen=now,
    )
    base.update(kw)
    return Listing(**base)


async def test_add_and_get_by_external(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="x1"))
        await s.commit()
    async with factory() as s:
        repo = ListingRepository(s)
        found = await repo.get_by_external("otodom", "x1")
        assert found is not None and found.external_id == "x1"
        missing = await repo.get_by_external("otodom", "nope")
        assert missing is None


async def test_list_active_and_count(engine):
    factory = await _setup(engine)
    async with factory() as s:
        repo = ListingRepository(s)
        await repo.add(_listing(external_id="a1"))
        await repo.add(_listing(external_id="a2"))
        await repo.add(_listing(external_id="g1", status=ListingStatus.GONE))
        await s.commit()
    async with factory() as s:
        repo = ListingRepository(s)
        assert await repo.count_active() == 2
        rows = await repo.list_active()
        assert {r.external_id for r in rows} == {"a1", "a2"}
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/repositories/test_listing_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.repositories.listings'`.

- [ ] **Step 3: Zaimplementuj repozytorium**

`src/realestate/repositories/__init__.py`:
```python
```

`src/realestate/repositories/listings.py`:
```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from realestate.models.enums import ListingStatus
from realestate.models.listing import Listing


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_external(self, source_id: str, external_id: str) -> Listing | None:
        stmt = select(Listing).where(
            Listing.source_id == source_id,
            Listing.external_id == external_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, listing: Listing) -> Listing:
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Listing]:
        stmt = (
            select(Listing)
            .where(Listing.status == ListingStatus.ACTIVE)
            .order_by(Listing.last_seen.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_active(self) -> int:
        stmt = select(func.count()).select_from(Listing).where(
            Listing.status == ListingStatus.ACTIVE
        )
        return (await self.session.execute(stmt)).scalar_one()
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `uv run pytest tests/repositories/test_listing_repository.py -v`
Expected: PASS (oba testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/repositories/ tests/repositories/test_listing_repository.py
git commit -m "feat: ListingRepository (upsert/get/list/count)"
```

---

### Task 8: Szkielet aplikacji FastAPI + healthcheck (DB + pgvector)

**Files:**
- Create: `src/realestate/api/__init__.py`
- Create: `src/realestate/api/app.py`
- Create: `src/realestate/db/health.py`
- Test: `tests/api/test_health.py`

**Interfaces:**
- Consumes: `get_settings`, `create_engine`, `text` query.
- Produces:
  - `check_database(engine) -> bool` — true gdy `SELECT 1` działa i rozszerzenie `vector` jest obecne.
  - `create_app() -> FastAPI` z endpointem `GET /health` → `{"status": "ok", "database": true}` (200) lub `{"status": "degraded", "database": false}` (503).
  - `app = create_app()` na poziomie modułu (dla `uvicorn realestate.api.app:app`).

- [ ] **Step 1: Napisz failujący test (z nadpisaniem zależności DB)**

`tests/api/test_health.py`:
```python
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app, get_db_health


async def test_health_ok():
    app = create_app()
    app.dependency_overrides[get_db_health] = lambda: True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": True}


async def test_health_degraded_when_db_down():
    app = create_app()
    app.dependency_overrides[get_db_health] = lambda: False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["database"] is False
```

- [ ] **Step 2: Uruchom test — ma faliować**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'realestate.api.app'`.

- [ ] **Step 3: Zaimplementuj healthcheck DB i aplikację**

`src/realestate/db/health.py`:
```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            ext = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            return ext.scalar_one_or_none() == 1
    except Exception:
        return False
```

`src/realestate/api/__init__.py`:
```python
```

`src/realestate/api/app.py`:
```python
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from realestate.config import get_settings
from realestate.db.engine import create_engine
from realestate.db.health import check_database


async def get_db_health() -> bool:
    engine = create_engine(get_settings().database_url)
    try:
        return await check_database(engine)
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Agregator nieruchomości")

    @app.get("/health")
    async def health(db_ok: bool = Depends(get_db_health)) -> JSONResponse:
        if db_ok:
            return JSONResponse({"status": "ok", "database": True})
        return JSONResponse({"status": "degraded", "database": False}, status_code=503)

    return app


app = create_app()
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: PASS (oba testy).

- [ ] **Step 5: Uruchom pełną zestaw testów + lint**

Run: `uv run pytest && uv run ruff check .`
Expected: wszystkie testy PASS; ruff bez błędów.

- [ ] **Step 6: Commit**

```bash
git add src/realestate/api/ src/realestate/db/health.py tests/api/test_health.py
git commit -m "feat: szkielet FastAPI + healthcheck DB/pgvector"
```

---

## Definicja ukończenia (Plan 1)
- `uv run pytest` zielony; `uv run ruff check .` bez błędów.
- `docker compose up -d db` + `uv run alembic upgrade head` tworzy schemat z rozszerzeniem `vector`.
- `uv run uvicorn realestate.api.app:app` wystawia `GET /health` (200/503 zależnie od DB).
- Repozytorium ofert działa na realnym Postgresie+pgvector (testcontainers).
- `AGENTS.md` + symlink `CLAUDE.md` obecne; sekrety poza repo.
