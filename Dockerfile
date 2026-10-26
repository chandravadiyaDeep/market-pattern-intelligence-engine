# Production container for the Market Pattern Intelligence Engine FastAPI API.
FROM python:3.12-slim

# Use unbuffered logs and keep image installation straightforward.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPIE_MODE=production \
    MPIE_DATABASE_PATH=/data/mpie.sqlite3

WORKDIR /app

# Install runtime package and source resources.
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY resources ./resources
COPY docs ./docs

RUN python -m pip install --upgrade pip && python -m pip install .

# For Render, mount a persistent disk at /data while the database uses SQLite.
RUN mkdir -p /data

# Render provides PORT at runtime; keep 10000 as the local Docker default.
CMD ["sh", "-c", "uvicorn market_engine.api:app --host 0.0.0.0 --port ${PORT:-10000}"]
