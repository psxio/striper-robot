# Stage 1: Build — install dependencies in a virtual environment
FROM python:3.12-slim AS builder

WORKDIR /build

COPY backend/requirements.txt ./backend/
RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r backend/requirements.txt

COPY striper_pathgen/ ./striper_pathgen/
RUN /venv/bin/pip install --no-cache-dir -e ./striper_pathgen/

# Stage 2: Runtime — lean image with only what's needed to run
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /venv /venv
COPY --from=builder /build/striper_pathgen/ ./striper_pathgen/
COPY backend/ ./backend/
COPY site/ ./site/

ENV PATH="/venv/bin:$PATH"

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /app/backend/data && \
    chown -R appuser:appgroup /app/backend/data

USER appuser

# NOTE: Mount a persistent volume at /app/backend/data to preserve the database.
# Example: docker run -v strype_data:/app/backend/data ...
# Without a volume, ALL DATA IS LOST on container restart.

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/api/health')"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 30"]
