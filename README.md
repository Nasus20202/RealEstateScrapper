# Agregator ofert nieruchomości (Trójmiasto)

Lokalna aplikacja agregująca oferty mieszkań z wielu portali. Patrz `docs/`.

## Szybki start (dev)

    uv sync --extra dev
    docker compose up -d db
    uv run pytest
