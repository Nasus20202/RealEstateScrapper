# Backend API (FastAPI + Playwright/chromium) — Python 3.14 via uv.
# Pinned: uv 0.11.23 on Debian 13 (trixie). Deliberately NOT Alpine — Playwright's
# Chromium binaries are glibc-only and `playwright install --with-deps` uses apt.
FROM ghcr.io/astral-sh/uv:0.11.23-python3.14-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Dependencies first (better layer caching) — no project, no dev deps.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Playwright chromium + its system libraries (needed for scraping).
RUN uv run playwright install --with-deps chromium

# 3) Application code + Alembic, then install the project itself.
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
RUN uv sync --frozen --no-dev

# 4) Entrypoint: run migrations, then start the API.
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
