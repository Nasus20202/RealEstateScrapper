from realestate.config import Settings, get_settings


def test_get_embedding_dim_reads_env(monkeypatch):
    from realestate.config import get_embedding_dim

    monkeypatch.setenv("EMBEDDING_DIM", "256")
    assert get_embedding_dim() == 256
    monkeypatch.delenv("EMBEDDING_DIM", raising=False)
    assert get_embedding_dim() == 1536


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


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    first = get_settings()
    second = get_settings()
    assert first is second
    assert first.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"
