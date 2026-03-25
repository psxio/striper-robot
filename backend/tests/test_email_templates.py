"""Tests for all email templates in dev mode (no SendGrid key required)."""

import pytest

from backend.services import email_service


# --- Original templates ---

@pytest.mark.asyncio
async def test_send_welcome_email():
    result = await email_service.send_welcome_email("test@example.com", "Test User")
    assert result is True


@pytest.mark.asyncio
async def test_send_password_reset_email():
    result = await email_service.send_password_reset_email("test@example.com", "token123")
    assert result is True


@pytest.mark.asyncio
async def test_send_verification_email():
    result = await email_service.send_verification_email("test@example.com", "vtoken")
    assert result is True


@pytest.mark.asyncio
async def test_send_robot_shipped_email():
    result = await email_service.send_robot_shipped_email("test@example.com", "1Z999AA10123")
    assert result is True


@pytest.mark.asyncio
async def test_send_robot_delivered_email():
    result = await email_service.send_robot_delivered_email("test@example.com")
    assert result is True


@pytest.mark.asyncio
async def test_send_schedule_created_email():
    result = await email_service.send_schedule_created_email("test@example.com", "North Lot", "weekly")
    assert result is True


@pytest.mark.asyncio
async def test_send_job_completed_email():
    result = await email_service.send_job_completed_email("test@example.com", "North Lot", "2026-04-01")
    assert result is True


# --- Phase 4 new templates ---

@pytest.mark.asyncio
async def test_send_invoice_email():
    result = await email_service.send_invoice_email("test@example.com", "99.00", "pro")
    assert result is True


@pytest.mark.asyncio
async def test_send_invoice_email_with_url():
    result = await email_service.send_invoice_email("test@example.com", "299.00", "robot", "https://stripe.com/inv_123")
    assert result is True


@pytest.mark.asyncio
async def test_send_payment_failed_email():
    result = await email_service.send_payment_failed_email("test@example.com", "pro")
    assert result is True


@pytest.mark.asyncio
async def test_send_subscription_cancelled_email():
    result = await email_service.send_subscription_cancelled_email("test@example.com", "robot")
    assert result is True


@pytest.mark.asyncio
async def test_send_renewal_reminder_email():
    result = await email_service.send_renewal_reminder_email("test@example.com", "pro", "2026-04-15")
    assert result is True


@pytest.mark.asyncio
async def test_send_claim_confirmation_email():
    result = await email_service.send_claim_confirmation_email("test@example.com", "STR-001", "North lot unit")
    assert result is True


@pytest.mark.asyncio
async def test_send_claim_confirmation_email_no_name():
    result = await email_service.send_claim_confirmation_email("test@example.com", "STR-002")
    assert result is True


@pytest.mark.asyncio
async def test_send_maintenance_due_email():
    result = await email_service.send_maintenance_due_email("test@example.com", "STR-001", "nozzle inspection")
    assert result is True


@pytest.mark.asyncio
async def test_send_low_paint_alert_email():
    result = await email_service.send_low_paint_alert_email("test@example.com", "STR-001", 12)
    assert result is True


@pytest.mark.asyncio
async def test_send_connectivity_lost_email():
    result = await email_service.send_connectivity_lost_email("test@example.com", "STR-001", "2026-03-25T10:00:00Z")
    assert result is True


@pytest.mark.asyncio
async def test_send_schedule_updated_email():
    result = await email_service.send_schedule_updated_email("test@example.com", "North Lot", "updated")
    assert result is True


@pytest.mark.asyncio
async def test_send_schedule_updated_email_deleted():
    result = await email_service.send_schedule_updated_email("test@example.com", "South Lot", "deleted")
    assert result is True


@pytest.mark.asyncio
async def test_send_job_created_email():
    result = await email_service.send_job_created_email("test@example.com", "East Lot", "2026-04-10")
    assert result is True


# --- Edge cases ---

@pytest.mark.asyncio
async def test_send_email_empty_to_still_returns_true_in_dev():
    """Dev mode logs instead of sending, even with empty addresses."""
    result = await email_service.send_welcome_email("", "Nobody")
    assert result is True
