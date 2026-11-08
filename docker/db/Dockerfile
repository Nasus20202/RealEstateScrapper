FROM postgres:18.6-trixie@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-pgvector \
    && rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=5s --timeout=5s --retries=5 \
  CMD pg_isready -U realestate
