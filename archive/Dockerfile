# ============================================================================
# Dockerfile — Striper Dashboard
#
# Builds a lightweight container for the FastAPI dashboard server.
#
# Build:
#   docker build -t striper-dashboard .
#
# Run:
#   docker run -p 8100:8000 striper-dashboard
#
# Or use docker-compose:
#   docker compose up
# ============================================================================
FROM python:3.11-slim

LABEL maintainer="Striper Robotics"
LABEL description="Striper parking-lot robot dashboard"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (none required for dashboard, but keep a layer
# in case we add C extensions later)
RUN apt-get update && \
    apt-get install -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/requirements.txt

# Copy the pathgen library (used by the paths router for template generation)
COPY striper_ws/src/striper_pathgen/ /app/striper_ws/src/striper_pathgen/

# Install pathgen as a package so the dashboard can import it
RUN pip install --no-cache-dir /app/striper_ws/src/striper_pathgen/

# Copy the dashboard application
COPY dashboard/ /app/dashboard/

# Expose the default dashboard port
EXPOSE 8000

# Create a directory for persistent data (SQLite database)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# Run the dashboard server
CMD ["uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
