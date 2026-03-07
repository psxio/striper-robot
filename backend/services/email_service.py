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
