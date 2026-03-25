"""Shipping integration service. Uses EasyPost when configured, returns mock data in dev/test mode.

All external HTTP calls go through the easypost_breaker circuit breaker to
prevent cascading failures when the EasyPost API is down.
"""

import logging
import random
import uuid
from datetime import datetime, timezone

import httpx

from ..config import settings
from .circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger("strype.shipping")

# Circuit breaker: open after 5 consecutive failures, retry after 60s
easypost_breaker = CircuitBreaker("easypost", failure_threshold=5, recovery_timeout=60)

EASYPOST_BASE = "https://api.easypost.com/v2"
EASYPOST_TIMEOUT = 10.0  # seconds

# Default robot kit box dimensions (inches) and weight (oz)
DEFAULT_PARCEL = {
    "length": 24,
    "width": 18,
    "height": 12,
    "weight": 800,  # 50 lbs
}


def _is_dev_mode() -> bool:
    """Return True if we should use mock data instead of real API calls."""
    return settings.ENV in ("dev", "test")


def _require_api_key() -> None:
    """Raise RuntimeError in production if EasyPost API key is not configured."""
    if not _is_dev_mode() and not settings.EASYPOST_API_KEY:
        raise RuntimeError(
            "EASYPOST_API_KEY is not configured. "
            "Set it in environment variables or use ENV=dev for mock mode."
        )


async def _easypost_post(path: str, json: dict) -> dict:
    """POST to EasyPost API with auth, timeout, and error handling."""
    async with httpx.AsyncClient(timeout=EASYPOST_TIMEOUT) as client:
        resp = await client.post(
            f"{EASYPOST_BASE}{path}",
            auth=(settings.EASYPOST_API_KEY, ""),
            json=json,
        )
        resp.raise_for_status()
        return resp.json()


async def _easypost_get(path: str, params: dict | None = None) -> dict:
    """GET from EasyPost API with auth, timeout, and error handling."""
    async with httpx.AsyncClient(timeout=EASYPOST_TIMEOUT) as client:
        resp = await client.get(
            f"{EASYPOST_BASE}{path}",
            auth=(settings.EASYPOST_API_KEY, ""),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


async def create_shipment(to_address: dict, weight_oz: int = 800) -> dict:
    """Create a shipment and retrieve available rates.

    Args:
        to_address: Destination address dict with keys: name, street1, city, state, zip, country.
        weight_oz: Package weight in ounces (default 800 = 50 lbs for a robot kit).

    Returns:
        Dict with shipment id, tracking_number, label_url, and rates list.
    """
    _require_api_key()
    if _is_dev_mode():
        mock_id = f"shp_mock_{uuid.uuid4().hex[:12]}"
        logger.info(
            "Shipment (dev mode, not created):\n  To: %s\n  Weight: %d oz\n  ID: %s",
            to_address.get("name", "unknown"),
            weight_oz,
            mock_id,
        )
        return {
            "id": mock_id,
            "tracking_number": "MOCK1234567890",
            "label_url": "https://example.com/mock-label.pdf",
            "rates": [
                {"id": "rate_mock", "carrier": "UPS", "service": "Ground", "rate": "45.00"}
            ],
        }

    parcel = {**DEFAULT_PARCEL, "weight": weight_oz}

    async def _call():
        data = await _easypost_post("/shipments", {
            "shipment": {
                "from_address": settings.SHIP_FROM_ADDRESS,
                "to_address": to_address,
                "parcel": parcel,
            }
        })
        return {
            "id": data["id"],
            "tracking_number": data.get("tracking_code", ""),
            "label_url": "",
            "rates": [
                {"id": r["id"], "carrier": r["carrier"], "service": r["service"], "rate": r["rate"]}
                for r in data.get("rates", [])
            ],
        }

    return await easypost_breaker.call(_call)


async def buy_label(shipment_id: str, rate_id: str) -> dict:
    """Purchase a shipping label for a shipment at the selected rate.

    Args:
        shipment_id: The shipment ID from create_shipment().
        rate_id: The chosen rate ID from the shipment's rates list.

    Returns:
        Dict with tracking_number and label_url.
    """
    _require_api_key()
    if _is_dev_mode():
        tracking = f"MOCK{random.randint(1000000000, 9999999999)}"
        logger.info(
            "Label purchase (dev mode, not purchased):\n  Shipment: %s\n  Rate: %s\n  Tracking: %s",
            shipment_id,
            rate_id,
            tracking,
        )
        return {
            "tracking_number": tracking,
            "label_url": "https://example.com/mock-label.pdf",
        }

    async def _call():
        data = await _easypost_post(f"/shipments/{shipment_id}/buy", {
            "rate": {"id": rate_id},
        })
        return {
            "tracking_number": data.get("tracking_code", ""),
            "label_url": data.get("postage_label", {}).get("label_url", ""),
        }

    return await easypost_breaker.call(_call)


async def create_return_label(
    customer_address: dict,
    weight_oz: int = 800,
) -> dict:
    """Create a prepaid return shipping label (reverse shipment).

    Args:
        customer_address: Customer's address (the return origin).
        weight_oz: Package weight in ounces.

    Returns:
        Dict with tracking_number and label_url for the return shipment.
    """
    _require_api_key()
    if _is_dev_mode():
        tracking = f"MOCKRET{random.randint(1000000, 9999999)}"
        logger.info(
            "Return label (dev mode, not created):\n  From: %s\n  Tracking: %s",
            customer_address.get("name", "unknown"),
            tracking,
        )
        return {
            "tracking_number": tracking,
            "label_url": "https://example.com/mock-return-label.pdf",
        }

    parcel = {**DEFAULT_PARCEL, "weight": weight_oz}

    async def _call():
        # Create reverse shipment (customer → warehouse)
        data = await _easypost_post("/shipments", {
            "shipment": {
                "from_address": customer_address,
                "to_address": settings.SHIP_FROM_ADDRESS,
                "parcel": parcel,
                "is_return": True,
            }
        })
        # Auto-buy cheapest rate
        rates = data.get("rates", [])
        if not rates:
            raise ValueError("No return shipping rates available")
        cheapest = min(rates, key=lambda r: float(r.get("rate", "9999")))
        bought = await _easypost_post(f"/shipments/{data['id']}/buy", {
            "rate": {"id": cheapest["id"]},
        })
        return {
            "tracking_number": bought.get("tracking_code", ""),
            "label_url": bought.get("postage_label", {}).get("label_url", ""),
        }

    return await easypost_breaker.call(_call)


async def get_tracking(tracking_number: str) -> dict:
    """Get tracking status and events for a shipment.

    Args:
        tracking_number: The carrier tracking number.

    Returns:
        Dict with tracking_number, status, eta, and events list.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    _require_api_key()
    if _is_dev_mode():
        logger.info("Tracking lookup (dev mode):\n  Tracking: %s", tracking_number)
        return {
            "tracking_number": tracking_number,
            "status": "in_transit",
            "eta": "2-5 business days",
            "events": [
                {"description": "Shipment created", "timestamp": now_iso}
            ],
        }

    async def _call():
        data = await _easypost_get("/trackers", params={"tracking_code": tracking_number})
        trackers = data.get("trackers", [])
        tracker = trackers[0] if trackers else {}
        return {
            "tracking_number": tracking_number,
            "status": tracker.get("status", "unknown"),
            "eta": tracker.get("est_delivery_date", "unknown"),
            "events": [
                {"description": e.get("message", ""), "timestamp": e.get("datetime", "")}
                for e in tracker.get("tracking_details", [])
            ],
        }

    return await easypost_breaker.call(_call)
