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
