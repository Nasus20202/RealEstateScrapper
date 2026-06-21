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
