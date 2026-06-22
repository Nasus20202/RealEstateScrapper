import pytest


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch, pg_url):
    monkeypatch.setenv("DATABASE_URL", pg_url)
