"""Shared pytest fixtures for dashboard API tests."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI

from dashboard.backend.routers import jobs, paths, robot
from dashboard.backend.services import job_store
from dashboard.backend.services.ros_bridge import RosBridge


@pytest.fixture()
def tmp_db(tmp_path):
    """Return a temporary database file path for test isolation."""
    return tmp_path / "test_jobs.db"


@pytest.fixture()
def mock_ros_bridge():
    """Create a fresh RosBridge instance (mock mode) without starting the sim loop."""
    bridge = RosBridge()
    bridge.start = AsyncMock()
    bridge.stop = AsyncMock()
    return bridge


@pytest_asyncio.fixture()
async def app(tmp_db, mock_ros_bridge):
    """Create a fresh FastAPI test application."""
    test_app = FastAPI()
    test_app.include_router(jobs.router)
    test_app.include_router(robot.router)
    test_app.include_router(paths.router)

    with patch.object(job_store, "DB_PATH", tmp_db):
        with patch("dashboard.backend.routers.jobs.ros_bridge", mock_ros_bridge):
            with patch("dashboard.backend.routers.robot.ros_bridge", mock_ros_bridge):
                await job_store.init_db()
                yield test_app


@pytest_asyncio.fixture()
async def client(app):
    """Async HTTP client wired to the test app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
