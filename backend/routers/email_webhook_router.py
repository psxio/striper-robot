"""SendGrid Event Webhook receiver for bounce/unsubscribe tracking."""

import logging
from typing import Any

from fastapi import APIRouter, Request

from ..services import email_store

router = APIRouter(prefix="/api/webhooks/email", tags=["webhooks"])
logger = logging.getLogger("strype.email_webhook")


@router.post("/sendgrid")
async def sendgrid_webhook(request: Request):
    """Process SendGrid Event Webhook payload.

    SendGrid sends a JSON array of event objects. We record each event
    for suppression tracking. Deduplicates via sg_event_id.

    Note: Signature verification is not implemented in v1. The endpoint
    relies on URL obscurity + HTTPS. TODO: Add ECDSA verification via
    SENDGRID_WEBHOOK_VERIFICATION_KEY when moving to production.
    """
    try:
        events: list[dict[str, Any]] = await request.json()
    except Exception:
        logger.warning("Invalid JSON in SendGrid webhook payload")
        return {"ok": True}  # Return 200 to prevent retries

    processed = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        email = event.get("email", "")
        event_type = event.get("event", "")
        if not email or not event_type:
            continue

        await email_store.record_email_event(
            email=email,
            event_type=event_type,
            reason=event.get("reason", "") or event.get("response", ""),
            sg_event_id=event.get("sg_event_id"),
            sg_message_id=event.get("sg_message_id", ""),
        )
        processed += 1

    if processed:
        logger.info("Processed %d SendGrid event(s)", processed)
    return {"ok": True}
