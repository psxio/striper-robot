"""Tests for the shipping service (dev/mock mode)."""

import pytest

from backend.services.shipping_service import (
    buy_label,
    create_return_label,
    create_shipment,
    get_tracking,
)

SAMPLE_ADDRESS = {
    "name": "Jane Doe",
    "street1": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip": "62701",
    "country": "US",
}


@pytest.mark.asyncio
async def test_create_shipment_returns_valid_structure():
    """create_shipment returns a dict with id, tracking_number, label_url, and rates."""
    result = await create_shipment(SAMPLE_ADDRESS)
    assert "id" in result
    assert "tracking_number" in result
    assert "label_url" in result
    assert "rates" in result
    assert isinstance(result["rates"], list)
    assert len(result["rates"]) > 0
    assert result["id"].startswith("shp_mock_")


@pytest.mark.asyncio
async def test_buy_label_returns_tracking_and_label():
    """buy_label returns a dict with tracking_number and label_url."""
    result = await buy_label("shp_mock_abc123", "rate_mock")
    assert "tracking_number" in result
    assert "label_url" in result
    assert result["tracking_number"].startswith("MOCK")
    assert result["label_url"].endswith(".pdf")


@pytest.mark.asyncio
async def test_create_return_label_returns_tracking_and_label():
    """create_return_label returns tracking_number and label_url for returns."""
    result = await create_return_label("assign_001")
    assert "tracking_number" in result
    assert "label_url" in result
    assert result["tracking_number"].startswith("MOCKRET")
    assert "return" in result["label_url"]


@pytest.mark.asyncio
async def test_get_tracking_returns_status_and_events():
    """get_tracking returns tracking info with status and an events list."""
    result = await get_tracking("MOCK1234567890")
    assert result["tracking_number"] == "MOCK1234567890"
    assert result["status"] == "in_transit"
    assert "eta" in result
    assert isinstance(result["events"], list)
    assert len(result["events"]) > 0
    event = result["events"][0]
    assert "description" in event
    assert "timestamp" in event


@pytest.mark.asyncio
async def test_shipment_rates_have_expected_fields():
    """Shipment rates include carrier, service, rate, and id fields."""
    result = await create_shipment(SAMPLE_ADDRESS, weight_oz=320)
    rate = result["rates"][0]
    assert "id" in rate
    assert "carrier" in rate
    assert "service" in rate
    assert "rate" in rate
    assert rate["carrier"] == "UPS"
    assert rate["service"] == "Ground"
    assert rate["rate"] == "45.00"
