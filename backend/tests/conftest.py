"""Shared test fixtures for the Strype Cloud backend tests."""

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test database before importing app
_fd, _tmp = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_PATH"] = _tmp
os.environ["DATABASE_URL"] = ""

from backend.main import app  # noqa: E402
from backend.database import init_db  # noqa: E402
from backend.rate_limit import limiter  # noqa: E402

# Disable rate limiting for all tests (re-enabled selectively in test_hardening.py)
limiter.enabled = False


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create a fresh database for each test."""
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = tmp_path
    os.environ["DATABASE_URL"] = ""
    from backend.config import settings
    settings.DATABASE_PATH = os.environ["DATABASE_PATH"]
    settings.DATABASE_URL = ""
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


@pytest_asyncio.fixture
async def pro_client(client):
    """Client with a registered Pro user."""
    resp = await client.post("/api/auth/register", json={
        "email": "pro@example.com",
        "password": "propass123",
        "name": "Pro User",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    client.headers["Authorization"] = f"Bearer {token}"
    from backend.services.billing_store import set_user_plan
    await set_user_plan(user_id, "pro")
    yield client


@pytest_asyncio.fixture
async def admin_client(client):
    """Client with an admin user."""
    resp = await client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "adminpass123",
        "name": "Admin User",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    client.headers["Authorization"] = f"Bearer {token}"
    from backend.services.admin_store import set_admin
    await set_admin(user_id, True)
    yield client
