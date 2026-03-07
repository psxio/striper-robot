"""Billing routes: Stripe Checkout, webhook, and customer portal."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..services import billing_store, user_store

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = logging.getLogger("strype.billing")


def _stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_ID)


def _get_safe_origin(request: Request) -> str:
    """Return a safe redirect origin, preferring FRONTEND_URL config."""
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL.rstrip("/")
    origin = request.headers.get("origin", "")
    if origin:
        allowed = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        if "*" not in allowed and origin not in allowed:
            origin = ""
    return origin or "http://localhost:8000"


async def _is_event_processed(event_id: str) -> bool:
    """Check if a webhook event has already been processed (DB-based idempotency)."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT 1 FROM webhook_events WHERE event_id = ?", (event_id,)
        )
        return await cursor.fetchone() is not None


async def _mark_event_processed(event_id: str) -> None:
    """Record a webhook event as processed."""
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            "INSERT OR IGNORE INTO webhook_events (event_id, processed_at) VALUES (?, ?)",
            (event_id, now),
        )
        await db.commit()


@router.post("/create-checkout")
async def create_checkout(request: Request, user: dict = Depends(get_current_user)):
    """Create a Stripe Checkout session for Pro plan upgrade."""
    if not _stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Get or create Stripe customer (check existing first to prevent race condition)
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        # Re-read from DB to handle concurrent requests
        fresh_user = await user_store.get_user_by_id(user["id"])
        customer_id = fresh_user.get("stripe_customer_id") if fresh_user else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": user["id"]},
        )
        customer_id = customer.id
        async for db in get_db():
            await db.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ? AND stripe_customer_id IS NULL",
                (customer_id, user["id"]),
            )
            await db.commit()

    origin = _get_safe_origin(request)
    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{origin}/platform.html?billing=success",
            cancel_url=f"{origin}/platform.html?billing=cancel",
            metadata={"user_id": user["id"]},
        )
    except stripe.error.StripeError as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=502, detail="Payment service unavailable")
    logger.info("Checkout session created for user %s", user["id"])
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    if not _stripe_configured() or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # DB-based idempotency check
    event_id = event.get("id", "")
    if event_id and await _is_event_processed(event_id):
        return {"ok": True}

    event_type = event["type"]
    logger.info("Processing webhook event: %s (%s)", event_type, event_id)

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        if user_id and session.get("subscription"):
            await billing_store.create_subscription(
                user_id=user_id,
                stripe_customer_id=session["customer"],
                stripe_subscription_id=session["subscription"],
                plan="pro",
                status="active",
            )

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await billing_store.update_subscription_status(
            stripe_subscription_id=subscription["id"],
            status="cancelled",
        )

    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        status = subscription.get("status", "active")
        # Map Stripe statuses to our statuses
        if status in ("past_due", "unpaid"):
            await billing_store.update_subscription_status(
                stripe_subscription_id=subscription["id"],
                status="past_due",
            )
        elif status == "active":
            await billing_store.update_subscription_status(
                stripe_subscription_id=subscription["id"],
                status="active",
                plan="pro",
            )

    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        sub_id = invoice.get("subscription")
        if sub_id:
            await billing_store.update_subscription_status(
                stripe_subscription_id=sub_id,
                status="past_due",
            )
            logger.warning("Payment failed for subscription %s", sub_id)

    elif event_type == "invoice.paid":
        invoice = event["data"]["object"]
        sub_id = invoice.get("subscription")
        if sub_id:
            await billing_store.update_subscription_status(
                stripe_subscription_id=sub_id,
                status="active",
                plan="pro",
            )

    # Mark event as processed
    if event_id:
        await _mark_event_processed(event_id)

    return {"ok": True}


@router.get("/portal")
async def billing_portal(request: Request, user: dict = Depends(get_current_user)):
    """Get Stripe Customer Portal URL for self-service management."""
    if not _stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe not configured")

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    origin = _get_safe_origin(request)
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{origin}/platform.html",
        )
    except stripe.error.StripeError as e:
        logger.error("Stripe portal error: %s", e)
        raise HTTPException(status_code=502, detail="Payment service unavailable")
    return {"url": session.url}
