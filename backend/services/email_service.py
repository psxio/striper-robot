"""Email sending service. Uses SendGrid when configured, logs in dev mode."""

import logging
from typing import Optional

from ..config import settings

logger = logging.getLogger("strype.email")


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send a transactional email. Returns True if sent or logged successfully."""
    api_key = getattr(settings, "SENDGRID_API_KEY", "")
    from_email = getattr(settings, "FROM_EMAIL", "")

    if not api_key or not from_email:
        if settings.ENV == "dev":
            logger.info("Email (dev mode, not sent):\n  To: %s\n  Subject: %s\n  Body: %s", to, subject, html_body[:200])
            return True
        logger.warning("Email not sent (SENDGRID_API_KEY or FROM_EMAIL not configured): to=%s subject=%s", to, subject)
        return False

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": from_email, "name": "Strype Cloud"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
            )
            if resp.status_code in (200, 202):
                logger.info("Email sent to %s: %s", to, subject)
                return True
            logger.error("SendGrid error %s: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


async def send_password_reset_email(to: str, token: str, frontend_url: str = "") -> bool:
    """Send a password reset email with the reset token."""
    base = frontend_url.rstrip("/") or "http://localhost:8000"
    reset_url = f"{base}/platform.html?reset_token={token}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Strype Cloud</h2>
        <p>You requested a password reset. Click the link below to reset your password:</p>
        <p><a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background: #f59e0b; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Reset Password</a></p>
        <p style="color: #666; font-size: 13px;">Or copy this token: <code>{token}</code></p>
        <p style="color: #666; font-size: 13px;">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
    </div>
    """
    return await send_email(to, "Reset your Strype password", html)


async def send_welcome_email(to: str, name: str = "") -> bool:
    """Send a welcome email to a new user."""
    greeting = f"Hi {name}," if name else "Welcome,"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Welcome to Strype Cloud!</h2>
        <p>{greeting}</p>
        <p>Your account is ready. Start by creating your first parking lot and mapping out your line striping plan.</p>
        <p style="color: #666; font-size: 13px;">Need help? Reply to this email or visit our platform.</p>
    </div>
    """
    return await send_email(to, "Welcome to Strype Cloud", html)


async def send_robot_shipped_email(to: str, tracking_number: str) -> bool:
    """Notify user their robot has shipped."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Your Strype Robot Has Shipped!</h2>
        <p>Great news — your robot is on its way.</p>
        <p><strong>Tracking number:</strong> {tracking_number}</p>
        <p style="color: #666; font-size: 13px;">You can track your shipment status in your dashboard.</p>
    </div>
    """
    return await send_email(to, "Your Strype Robot Has Shipped", html)


async def send_robot_delivered_email(to: str) -> bool:
    """Notify user their robot has been delivered."""
    html = """
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Your Strype Robot Has Arrived!</h2>
        <p>Your robot has been marked as delivered. Log in to your dashboard to get started.</p>
        <p style="color: #666; font-size: 13px;">Need help setting up? Check our getting started guide in the platform.</p>
    </div>
    """
    return await send_email(to, "Your Strype Robot Has Arrived", html)


async def send_return_initiated_email(to: str, return_label_info: str = "") -> bool:
    """Notify user that a robot return has been initiated."""
    label_note = f"<p><strong>Return label:</strong> {return_label_info}</p>" if return_label_info else ""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Robot Return Initiated</h2>
        <p>A return has been initiated for your Strype robot. Please package it securely and ship it back.</p>
        {label_note}
        <p style="color: #666; font-size: 13px;">Contact support if you need assistance with the return process.</p>
    </div>
    """
    return await send_email(to, "Robot Return Instructions", html)


async def send_schedule_created_email(to: str, lot_name: str, frequency: str) -> bool:
    """Confirm a recurring schedule was created."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Recurring Schedule Created</h2>
        <p>A {frequency} schedule has been set up for <strong>{lot_name}</strong>.</p>
        <p>Jobs will be automatically created based on your schedule. You can manage it from your dashboard.</p>
    </div>
    """
    return await send_email(to, f"Schedule Created: {lot_name}", html)


async def send_job_completed_email(to: str, lot_name: str, date: str) -> bool:
    """Notify user a job has been completed."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Job Completed</h2>
        <p>The striping job for <strong>{lot_name}</strong> scheduled on {date} has been completed.</p>
        <p style="color: #666; font-size: 13px;">View details in your dashboard.</p>
    </div>
    """
    return await send_email(to, f"Job Completed: {lot_name}", html)


async def send_verification_email(to: str, token: str, frontend_url: str = "") -> bool:
    """Send email verification link."""
    base = frontend_url.rstrip("/") or "http://localhost:8000"
    verify_url = f"{base}/platform.html?verify_token={token}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Verify Your Email</h2>
        <p>Click the button below to verify your email address:</p>
        <p><a href="{verify_url}" style="display: inline-block; padding: 12px 24px; background: #f59e0b; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Verify Email</a></p>
        <p style="color: #666; font-size: 13px;">This link expires in 24 hours. If you didn't create an account, ignore this email.</p>
    </div>
    """
    return await send_email(to, "Verify your Strype email", html)


# ── Phase 4 email templates ──────────────────────────────────────────────────


async def send_invoice_email(to: str, amount: str, plan: str, invoice_url: str = "") -> bool:
    """Notify user of a paid invoice."""
    link = f'<p><a href="{invoice_url}" style="color: #f59e0b;">View invoice</a></p>' if invoice_url else ""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Payment Received</h2>
        <p>We received your payment of <strong>${amount}</strong> for the <strong>{plan}</strong> plan.</p>
        {link}
        <p style="color: #666; font-size: 13px;">Thank you for using Strype Cloud.</p>
    </div>
    """
    return await send_email(to, f"Payment received — ${amount}", html)


async def send_payment_failed_email(to: str, plan: str) -> bool:
    """Notify user that their payment failed."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #e53e3e;">Payment Failed</h2>
        <p>We were unable to process your payment for the <strong>{plan}</strong> plan.</p>
        <p>Please update your payment method to avoid service interruption.</p>
        <p><a href="/billing.html" style="display: inline-block; padding: 12px 24px; background: #f59e0b; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Update Billing</a></p>
    </div>
    """
    return await send_email(to, "Action required: payment failed", html)


async def send_subscription_cancelled_email(to: str, plan: str) -> bool:
    """Notify user their subscription has been cancelled."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Subscription Cancelled</h2>
        <p>Your <strong>{plan}</strong> plan has been cancelled. Your account has been downgraded to the free tier.</p>
        <p>You can resubscribe at any time from the billing page.</p>
        <p style="color: #666; font-size: 13px;">If this was a mistake, visit <a href="/billing.html" style="color: #f59e0b;">billing</a> to reactivate.</p>
    </div>
    """
    return await send_email(to, f"Subscription cancelled: {plan}", html)


async def send_renewal_reminder_email(to: str, plan: str, renewal_date: str) -> bool:
    """Remind user their subscription renews soon."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Subscription Renewal Reminder</h2>
        <p>Your <strong>{plan}</strong> plan renews on <strong>{renewal_date}</strong>.</p>
        <p>No action needed — your payment method will be charged automatically.</p>
        <p style="color: #666; font-size: 13px;">Manage your subscription at <a href="/billing.html" style="color: #f59e0b;">billing</a>.</p>
    </div>
    """
    return await send_email(to, f"Renewal reminder: {plan} plan on {renewal_date}", html)


async def send_claim_confirmation_email(to: str, robot_serial: str, friendly_name: str = "") -> bool:
    """Confirm a robot was claimed successfully."""
    name_part = f" ({friendly_name})" if friendly_name else ""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Robot Claimed!</h2>
        <p>Robot <strong>{robot_serial}</strong>{name_part} has been commissioned into your workspace.</p>
        <p>You can view its status and assign jobs from your dashboard.</p>
    </div>
    """
    return await send_email(to, f"Robot claimed: {robot_serial}", html)


async def send_maintenance_due_email(to: str, robot_serial: str, service_type: str) -> bool:
    """Alert that a robot has maintenance due."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Maintenance Due</h2>
        <p>Robot <strong>{robot_serial}</strong> has <strong>{service_type}</strong> maintenance due.</p>
        <p>Schedule service soon to keep your robot in peak condition.</p>
        <p style="color: #666; font-size: 13px;">View fleet status in <a href="/operations.html" style="color: #f59e0b;">Operations</a>.</p>
    </div>
    """
    return await send_email(to, f"Maintenance due: {robot_serial}", html)


async def send_low_paint_alert_email(to: str, robot_serial: str, paint_level_pct: int) -> bool:
    """Alert that a robot's paint level is low."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #e53e3e;">Low Paint Level</h2>
        <p>Robot <strong>{robot_serial}</strong> is at <strong>{paint_level_pct}%</strong> paint level.</p>
        <p>Refill the paint tank before the next scheduled job to avoid interruption.</p>
    </div>
    """
    return await send_email(to, f"Low paint: {robot_serial} at {paint_level_pct}%", html)


async def send_connectivity_lost_email(to: str, robot_serial: str, last_seen_at: str) -> bool:
    """Alert that a robot has gone offline."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #e53e3e;">Robot Offline</h2>
        <p>Robot <strong>{robot_serial}</strong> has not sent a heartbeat since <strong>{last_seen_at}</strong>.</p>
        <p>Check the robot's power, network connection, and cellular signal.</p>
        <p style="color: #666; font-size: 13px;">This alert triggers when a robot is offline for over 2 hours.</p>
    </div>
    """
    return await send_email(to, f"Robot offline: {robot_serial}", html)


async def send_schedule_updated_email(to: str, lot_name: str, change_type: str) -> bool:
    """Notify user a schedule was updated or deleted."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Schedule {change_type.title()}</h2>
        <p>The recurring schedule for <strong>{lot_name}</strong> has been {change_type}.</p>
        <p style="color: #666; font-size: 13px;">Manage schedules from your <a href="/platform.html" style="color: #f59e0b;">dashboard</a>.</p>
    </div>
    """
    return await send_email(to, f"Schedule {change_type}: {lot_name}", html)


async def send_job_created_email(to: str, lot_name: str, date: str) -> bool:
    """Notify user a job was auto-created from a recurring schedule."""
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">New Job Scheduled</h2>
        <p>A striping job for <strong>{lot_name}</strong> has been automatically scheduled for <strong>{date}</strong>.</p>
        <p style="color: #666; font-size: 13px;">This job was created from your recurring schedule. View it in your <a href="/platform.html" style="color: #f59e0b;">dashboard</a>.</p>
    </div>
    """
    return await send_email(to, f"Job scheduled: {lot_name} on {date}", html)
