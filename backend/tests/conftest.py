"""Shared test fixtures for the Strype Cloud backend tests."""

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test database before importing app
_tmp = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = _tmp

from backend.main import app  # noqa: E402
from backend.database import init_db  # noqa: E402
from backend.rate_limit import limiter  # noqa: E402

# Disable rate limiting for all tests (re-enabled selectively in test_hardening.py)
limiter.enabled = False


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create a fresh database for each test."""
    os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
    from backend.config import settings
    settings.DATABASE_PATH = os.environ["DATABASE_PATH"]
    await init_db()
    yield
    try:
        os.unlink(settings.DATABASE_PATH)
    except (FileNotFoundError, PermissionError):
        pass


@pytest_asyncio.fixture
async def client():
    """Unauthenticated async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    """Client with a registered and authenticated user."""
    resp = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "name": "Test User",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
