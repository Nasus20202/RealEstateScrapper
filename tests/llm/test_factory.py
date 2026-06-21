# tests/llm/test_factory.py
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
