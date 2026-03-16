"""Shipping integration service. Uses EasyPost when configured, returns mock data in dev mode."""

import logging
import random
import uuid
from datetime import datetime, timezone

from ..config import settings

logger = logging.getLogger("strype.shipping")


def _is_dev_mode() -> bool:
    """Return True if we should use mock data instead of real API calls."""
    return settings.ENV == "dev"


def _require_api_key() -> None:
    """Raise RuntimeError in production if EasyPost API key is not configured."""
    if not _is_dev_mode() and not getattr(settings, "EASYPOST_API_KEY", ""):
        raise RuntimeError(
            "EASYPOST_API_KEY is not configured. "
            "Set it in environment variables or use ENV=dev for mock mode."
        )


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
                {
                    "id": "rate_mock",
                    "carrier": "UPS",
                    "service": "Ground",
                    "rate": "45.00",
                }
            ],
        }

    # TODO: Implement real EasyPost API call
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(
    #         "https://api.easypost.com/v2/shipments",
    #         auth=(settings.EASYPOST_API_KEY, ""),
    #         json={
    #             "shipment": {
    #                 "from_address": settings.SHIP_FROM_ADDRESS,
    #                 "to_address": to_address,
    #                 "parcel": {"weight": weight_oz},
    #             }
    #         },
    #     )
    #     resp.raise_for_status()
    #     data = resp.json()
    #     return {
    #         "id": data["id"],
    #         "tracking_number": data.get("tracking_code", ""),
    #         "label_url": "",
    #         "rates": [
    #             {"id": r["id"], "carrier": r["carrier"], "service": r["service"], "rate": r["rate"]}
    #             for r in data.get("rates", [])
    #         ],
    #     }
    mock_id = f"shp_mock_{uuid.uuid4().hex[:12]}"
    logger.warning("EasyPost integration not yet implemented — returning mock data")
    return {
        "id": mock_id,
        "tracking_number": "MOCK1234567890",
        "label_url": "https://example.com/mock-label.pdf",
        "rates": [
            {
                "id": "rate_mock",
                "carrier": "UPS",
                "service": "Ground",
                "rate": "45.00",
            }
        ],
    }


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

    # TODO: Implement real EasyPost label purchase
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(
    #         f"https://api.easypost.com/v2/shipments/{shipment_id}/buy",
    #         auth=(settings.EASYPOST_API_KEY, ""),
    #         json={"rate": {"id": rate_id}},
    #     )
    #     resp.raise_for_status()
    #     data = resp.json()
    #     return {
    #         "tracking_number": data.get("tracking_code", ""),
    #         "label_url": data.get("postage_label", {}).get("label_url", ""),
    #     }
    tracking = f"MOCK{random.randint(1000000000, 9999999999)}"
    logger.warning("EasyPost label purchase not yet implemented — returning mock data")
    return {
        "tracking_number": tracking,
        "label_url": "https://example.com/mock-label.pdf",
    }


async def create_return_label(assignment_id: str) -> dict:
    """Create a prepaid return shipping label for a robot assignment.

    Args:
        assignment_id: The robot assignment ID to associate the return with.

    Returns:
        Dict with tracking_number and label_url for the return shipment.
    """
    _require_api_key()
    if _is_dev_mode():
        tracking = f"MOCKRET{random.randint(1000000, 9999999)}"
        logger.info(
            "Return label (dev mode, not created):\n  Assignment: %s\n  Tracking: %s",
            assignment_id,
            tracking,
        )
        return {
            "tracking_number": tracking,
            "label_url": "https://example.com/mock-return-label.pdf",
        }

    # TODO: Implement real EasyPost return label creation
    # This would create a shipment with from/to addresses swapped, then buy label.
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     # Look up assignment to get customer address, then create reverse shipment
    #     resp = await client.post(
    #         "https://api.easypost.com/v2/shipments",
    #         auth=(settings.EASYPOST_API_KEY, ""),
    #         json={
    #             "shipment": {
    #                 "from_address": customer_address,  # from assignment
    #                 "to_address": settings.SHIP_FROM_ADDRESS,
    #                 "parcel": {"weight": 800},
    #                 "is_return": True,
    #             }
    #         },
    #     )
    #     resp.raise_for_status()
    #     # Then buy the cheapest rate...
    tracking = f"MOCKRET{random.randint(1000000, 9999999)}"
    logger.warning("EasyPost return label not yet implemented — returning mock data")
    return {
        "tracking_number": tracking,
        "label_url": "https://example.com/mock-return-label.pdf",
    }


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
        logger.info(
            "Tracking lookup (dev mode):\n  Tracking: %s",
            tracking_number,
        )
        return {
            "tracking_number": tracking_number,
            "status": "in_transit",
            "eta": "2-5 business days",
            "events": [
                {
                    "description": "Shipment created",
                    "timestamp": now_iso,
                }
            ],
        }

    # TODO: Implement real EasyPost tracking lookup
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(
    #         f"https://api.easypost.com/v2/trackers",
    #         auth=(settings.EASYPOST_API_KEY, ""),
    #         params={"tracking_code": tracking_number},
    #     )
    #     resp.raise_for_status()
    #     data = resp.json()
    #     tracker = data["trackers"][0] if data.get("trackers") else {}
    #     return {
    #         "tracking_number": tracking_number,
    #         "status": tracker.get("status", "unknown"),
    #         "eta": tracker.get("est_delivery_date", "unknown"),
    #         "events": [
    #             {"description": e["message"], "timestamp": e["datetime"]}
    #             for e in tracker.get("tracking_details", [])
    #         ],
    #     }
    logger.warning("EasyPost tracking not yet implemented — returning mock data")
    return {
        "tracking_number": tracking_number,
        "status": "in_transit",
        "eta": "2-5 business days",
        "events": [
            {
                "description": "Shipment created",
                "timestamp": now_iso,
            }
        ],
    }
