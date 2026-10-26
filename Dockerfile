# Minimal production image for the Market Pattern Intelligence Engine API.
FROM python:3.12-slim

# Avoid buffered logs and prevent bytecode clutter in the container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPIE_MODE=production \
    MPIE_DATABASE_PATH=/data/mpie.sqlite3

WORKDIR /app

# Install only runtime dependencies through the package metadata.
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY resources ./resources
COPY docs ./docs

RUN python -m pip install --upgrade pip && python -m pip install .

# Railway volume should be mounted at /data to persist SQLite data.
RUN mkdir -p /data

# Railway provides PORT at runtime; default to 8000 for local Docker runs.
CMD ["sh", "-c", "uvicorn market_engine.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
