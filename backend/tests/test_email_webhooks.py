"""Tests for SendGrid email webhook processing and suppression."""

import pytest

from backend.services.email_store import is_email_suppressed, record_email_event


# --- email_store unit tests ---

@pytest.mark.asyncio
async def test_record_bounce_event(client):
    """Recording a bounce event stores it in the database."""
    await record_email_event("bounced@example.com", "bounce", reason="550 User unknown")
    assert await is_email_suppressed("bounced@example.com") is True


@pytest.mark.asyncio
async def test_record_unsubscribe_event(client):
    """Recording an unsubscribe event suppresses future emails."""
    await record_email_event("unsub@example.com", "unsubscribe")
    assert await is_email_suppressed("unsub@example.com") is True


@pytest.mark.asyncio
async def test_record_spamreport_event(client):
    """Spam report suppresses future emails."""
    await record_email_event("spam@example.com", "spamreport")
    assert await is_email_suppressed("spam@example.com") is True


@pytest.mark.asyncio
async def test_delivered_event_does_not_suppress(client):
    """Delivered events do not cause suppression."""
    await record_email_event("good@example.com", "delivered")
    assert await is_email_suppressed("good@example.com") is False


@pytest.mark.asyncio
async def test_clean_email_not_suppressed(client):
    """An email with no events is not suppressed."""
    assert await is_email_suppressed("clean@example.com") is False


@pytest.mark.asyncio
async def test_dedup_by_sg_event_id(client):
    """Duplicate sg_event_id is silently ignored (no error)."""
    await record_email_event("dup@example.com", "bounce", sg_event_id="evt_001")
    await record_email_event("dup@example.com", "bounce", sg_event_id="evt_001")  # Duplicate
    assert await is_email_suppressed("dup@example.com") is True


@pytest.mark.asyncio
async def test_case_insensitive_email(client):
    """Suppression check is case-insensitive."""
    await record_email_event("UPPER@EXAMPLE.COM", "bounce")
    assert await is_email_suppressed("upper@example.com") is True


# --- Webhook endpoint tests ---

@pytest.mark.asyncio
async def test_webhook_processes_bounce(client):
    """POST /api/webhooks/email/sendgrid processes bounce events."""
    resp = await client.post("/api/webhooks/email/sendgrid", json=[
        {"email": "webhook-bounce@example.com", "event": "bounce", "reason": "550", "sg_event_id": "wb001"},
    ])
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert await is_email_suppressed("webhook-bounce@example.com") is True


@pytest.mark.asyncio
async def test_webhook_processes_multiple_events(client):
    """Webhook processes multiple events in a single payload."""
    resp = await client.post("/api/webhooks/email/sendgrid", json=[
        {"email": "multi1@example.com", "event": "delivered", "sg_event_id": "m001"},
        {"email": "multi2@example.com", "event": "bounce", "sg_event_id": "m002"},
        {"email": "multi3@example.com", "event": "open", "sg_event_id": "m003"},
    ])
    assert resp.status_code == 200
    assert await is_email_suppressed("multi1@example.com") is False
    assert await is_email_suppressed("multi2@example.com") is True
    assert await is_email_suppressed("multi3@example.com") is False


@pytest.mark.asyncio
async def test_webhook_handles_empty_payload(client):
    """Webhook returns 200 on empty array."""
    resp = await client.post("/api/webhooks/email/sendgrid", json=[])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_handles_invalid_json(client):
    """Webhook returns 200 on invalid JSON (to prevent SendGrid retries)."""
    resp = await client.post(
        "/api/webhooks/email/sendgrid",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
