#!/usr/bin/env bash
# Entrypoint for the API container: apply DB migrations, then run uvicorn.
# DATABASE_URL and EMBEDDING_DIM must be provided via the environment
# (set by docker-compose). EMBEDDING_DIM must match the value used at run time.
set -euo pipefail

echo "[entrypoint] EMBEDDING_DIM=${EMBEDDING_DIM:-1536} — applying migrations..."
uv run alembic upgrade head

echo "[entrypoint] starting API on 0.0.0.0:8000 ..."
exec uv run uvicorn realestate.api.app:app --host 0.0.0.0 --port 8000
