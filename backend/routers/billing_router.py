"""Billing routes: Stripe Checkout, webhook, and customer portal."""

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_current_user
from ..config import settings
from ..services import billing_store, user_store

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = logging.getLogger("strype.billing")

# Webhook idempotency: track processed event IDs (capped at 10k)
_processed_events: set[str] = set()


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


@router.post("/create-checkout")
async def create_checkout(request: Request, user: dict = Depends(get_current_user)):
    """Create a Stripe Checkout session for Pro plan upgrade."""
    if not _stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Get or create Stripe customer
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": user["id"]},
        )
        customer_id = customer.id
        await user_store.update_profile(user["id"], email=None)
        from ..database import get_db
        async for db in get_db():
            await db.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
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
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Idempotency check
    event_id = event.get("id", "")
    if event_id in _processed_events:
        return {"ok": True}
    if len(_processed_events) >= 10000:
        _processed_events.clear()
    _processed_events.add(event_id)

    if event["type"] == "checkout.session.completed":
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

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await billing_store.update_subscription_status(
            stripe_subscription_id=subscription["id"],
            status="cancelled",
        )

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
