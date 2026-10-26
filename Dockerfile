# Docker image for the optional Render-hosted FastAPI API.
FROM python:3.12-slim

# Keep logs visible and configure a persistent database path for Render.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPIE_MODE=production \
    MPIE_DATABASE_PATH=/data/mpie.sqlite3

WORKDIR /app

# Install the Python package and its runtime resources.
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY resources ./resources
COPY docs ./docs

RUN python -m pip install --upgrade pip && python -m pip install .

# Render persistent disks should be mounted at /data.
RUN mkdir -p /data

# Render provides PORT; the fallback is useful for local Docker runs.
CMD ["sh", "-c", "uvicorn market_engine.api:app --host 0.0.0.0 --port ${PORT:-10000}"]
