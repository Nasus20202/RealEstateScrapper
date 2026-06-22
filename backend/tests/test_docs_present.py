from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

REQUIRED = {
    "README.md": ["Architektura", "Uruchomienie", "Konfiguracja"],
    "docs/architecture.md": ["Warstwy", "pgvector", "wyszukiwani"],
    "docs/running.md": ["docker compose", "uv run", "uvicorn", "frontend"],
    "docs/configuration.md": ["EMBEDDING_DIM", "LLM_", "scheduler"],
    "docs/adding-a-scraper.md": ["Scraper", "register", "RawListing"],
    "docs/testing.md": ["pytest", "testcontainers", "vitest"],
}


@pytest.mark.parametrize("path,needles", REQUIRED.items())
def test_doc_exists_and_mentions(path, needles):
    file = ROOT / path
    assert file.exists(), f"brak pliku dokumentacji: {path}"
    text = file.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path} nie zawiera oczekiwanego fragmentu: {needle!r}"
