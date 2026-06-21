import pytest

import realestate.scrapers.base as base


@pytest.fixture(autouse=True)
def _isolate_registry():
    saved = dict(base._REGISTRY)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
