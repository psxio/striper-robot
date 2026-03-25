"""Tests for telemetry monitoring: offline robots and low paint alerts."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from backend.database import get_db
from backend.services.telemetry_monitor import (
    _resolve_alert_recipients,
    check_offline_robots,
    check_low_paint,
    _alerted_offline,
    _alerted_low_paint,
)


async def _create_user(email: str, name: str = "Test") -> str:
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO users (id, email, password_hash, name, plan, created_at, updated_at)
               VALUES (?, ?, 'hash', ?, 'robot', ?, ?)""",
            (user_id, email, name, now, now),
        )
        await db.commit()
    return user_id


async def _create_org(user_id: str) -> str:
    org_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO organizations (id, name, slug, created_by_user_id, created_at, updated_at)
               VALUES (?, 'Test Org', ?, ?, ?, ?)""",
            (org_id, f"test-{org_id[:8]}", user_id, now, now),
        )
        await db.execute(
            """INSERT INTO memberships (id, organization_id, user_id, role, status, created_at, updated_at)
               VALUES (?, ?, ?, 'owner', 'active', ?, ?)""",
            (str(uuid.uuid4()), org_id, user_id, now, now),
        )
        await db.commit()
    return org_id


async def _create_robot(serial: str, last_seen_at: str | None = None) -> str:
    robot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO robots (id, serial_number, status, hardware_version, last_seen_at, created_at, updated_at)
               VALUES (?, ?, 'available', 'v1', ?, ?, ?)""",
            (robot_id, serial, last_seen_at, now, now),
        )
        await db.commit()
    return robot_id


async def _claim_robot(robot_id: str, org_id: str, user_id: str):
    claim_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO robot_claims
               (id, robot_id, organization_id, claim_code_hash, status, commissioning_status,
                claimed_by_user_id, claimed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'claimed', 'commissioned', ?, ?, ?, ?)""",
            (claim_id, robot_id, org_id, f"hash_{claim_id[:8]}", user_id, now, now, now),
        )
        await db.commit()


async def _insert_telemetry(robot_id: str, paint_level_pct: int | None = None, created_at: str | None = None):
    now = created_at or datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO robot_telemetry (robot_id, battery_pct, paint_level_pct, state, created_at)
               VALUES (?, 80, ?, 'idle', ?)""",
            (robot_id, paint_level_pct, now),
        )
        await db.commit()


@pytest.fixture(autouse=True)
def clear_dedup():
    """Clear dedup sets before each test."""
    _alerted_offline.clear()
    _alerted_low_paint.clear()
    yield
    _alerted_offline.clear()
    _alerted_low_paint.clear()


# --- Recipient Resolution ---

@pytest.mark.asyncio
async def test_resolve_recipients_via_claim(client):
    """Resolves email via robot_claims → org → membership → user."""
    user_id = await _create_user("owner@example.com")
    org_id = await _create_org(user_id)
    robot_id = await _create_robot("MON-001")
    await _claim_robot(robot_id, org_id, user_id)

    recipients = await _resolve_alert_recipients(robot_id)
    assert len(recipients) >= 1
    assert any(r["email"] == "owner@example.com" for r in recipients)


@pytest.mark.asyncio
async def test_resolve_recipients_unclaimed_robot(client):
    """Unclaimed robot with no assignment returns empty list."""
    robot_id = await _create_robot("MON-002")
    recipients = await _resolve_alert_recipients(robot_id)
    assert recipients == []


# --- Offline Robot Detection ---

@pytest.mark.asyncio
async def test_check_offline_detects_stale_robot(client):
    """Robot with last_seen_at > 2 hours ago triggers alert."""
    user_id = await _create_user("offline-alert@example.com")
    org_id = await _create_org(user_id)
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    robot_id = await _create_robot("MON-003", last_seen_at=stale_time)
    await _claim_robot(robot_id, org_id, user_id)

    count = await check_offline_robots(threshold_hours=2)
    assert count == 1
    assert robot_id in _alerted_offline


@pytest.mark.asyncio
async def test_check_offline_skips_recent_robot(client):
    """Robot with recent heartbeat is not flagged."""
    recent_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    await _create_robot("MON-004", last_seen_at=recent_time)

    count = await check_offline_robots(threshold_hours=2)
    assert count == 0


@pytest.mark.asyncio
async def test_check_offline_dedup_prevents_respam(client):
    """Second tick does not re-alert the same robot."""
    user_id = await _create_user("dedup@example.com")
    org_id = await _create_org(user_id)
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    robot_id = await _create_robot("MON-005", last_seen_at=stale_time)
    await _claim_robot(robot_id, org_id, user_id)

    count1 = await check_offline_robots(threshold_hours=2)
    assert count1 == 1

    count2 = await check_offline_robots(threshold_hours=2)
    assert count2 == 0  # Deduped


# --- Low Paint Detection ---

@pytest.mark.asyncio
async def test_check_low_paint_detects_below_threshold(client):
    """Robot with paint_level_pct < 15% triggers alert."""
    user_id = await _create_user("lowpaint@example.com")
    org_id = await _create_org(user_id)
    robot_id = await _create_robot("MON-006")
    await _claim_robot(robot_id, org_id, user_id)
    await _insert_telemetry(robot_id, paint_level_pct=10)

    count = await check_low_paint(threshold_pct=15)
    assert count == 1
    assert robot_id in _alerted_low_paint


@pytest.mark.asyncio
async def test_check_low_paint_skips_adequate_level(client):
    """Robot with paint above threshold is not flagged."""
    robot_id = await _create_robot("MON-007")
    await _insert_telemetry(robot_id, paint_level_pct=80)

    count = await check_low_paint(threshold_pct=15)
    assert count == 0


@pytest.mark.asyncio
async def test_check_low_paint_skips_no_telemetry(client):
    """Robot with no telemetry records is not flagged."""
    await _create_robot("MON-008")

    count = await check_low_paint(threshold_pct=15)
    assert count == 0


@pytest.mark.asyncio
async def test_low_paint_dedup_clears_after_refill(client):
    """After paint is refilled above threshold, the alert clears and can re-trigger."""
    user_id = await _create_user("refill@example.com")
    org_id = await _create_org(user_id)
    robot_id = await _create_robot("MON-009")
    await _claim_robot(robot_id, org_id, user_id)
    await _insert_telemetry(robot_id, paint_level_pct=8)

    count1 = await check_low_paint(threshold_pct=15)
    assert count1 == 1
    assert robot_id in _alerted_low_paint

    # Simulate refill — new telemetry with high paint
    await _insert_telemetry(robot_id, paint_level_pct=90)

    # Run again — should clear the dedup
    await check_low_paint(threshold_pct=15)
    assert robot_id not in _alerted_low_paint
