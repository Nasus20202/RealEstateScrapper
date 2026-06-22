FROM pgvector/pgvector:0.8.3-pg18-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-18-postgis-3 \
    && rm -rf /var/lib/apt/lists/*
