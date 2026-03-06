FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY site/ ./site/

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /app/backend/data && \
    chown -R appuser:appgroup /app/backend/data

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/health')"

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
