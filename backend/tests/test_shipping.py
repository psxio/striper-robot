"""Tests for the shipping service (dev/mock mode) and circuit breaker."""

import pytest

from backend.services.shipping_service import (
    buy_label,
    create_return_label,
    create_shipment,
    get_tracking,
    easypost_breaker,
)
from backend.services.circuit_breaker import CircuitBreaker, CircuitOpenError

SAMPLE_ADDRESS = {
    "name": "Jane Doe",
    "street1": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip": "62701",
    "country": "US",
}


# --- Shipping (dev/mock mode) ---

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
    result = await create_return_label(SAMPLE_ADDRESS)
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


# --- Circuit Breaker ---

@pytest.mark.asyncio
async def test_circuit_breaker_starts_closed():
    """New circuit breaker starts in closed state."""
    breaker = CircuitBreaker("test_svc", failure_threshold=3, recovery_timeout=1)
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_success_keeps_closed():
    """Successful calls keep the circuit closed."""
    breaker = CircuitBreaker("test_svc", failure_threshold=3, recovery_timeout=1)

    async def ok():
        return "ok"

    result = await breaker.call(ok)
    assert result == "ok"
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    """Circuit opens after N consecutive failures."""
    breaker = CircuitBreaker("test_svc", failure_threshold=3, recovery_timeout=60)

    async def fail():
        raise ConnectionError("down")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            await breaker.call(fail)

    assert breaker.state == "open"
    assert breaker.failure_count == 3


@pytest.mark.asyncio
async def test_circuit_open_rejects_immediately():
    """Open circuit raises CircuitOpenError without calling the function."""
    breaker = CircuitBreaker("test_svc", failure_threshold=2, recovery_timeout=60)
    call_count = 0

    async def fail():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("down")

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await breaker.call(fail)

    assert call_count == 2
    assert breaker.state == "open"

    # Next call should fail fast without executing the function
    with pytest.raises(CircuitOpenError) as exc_info:
        await breaker.call(fail)

    assert call_count == 2  # Not incremented — function was not called
    assert exc_info.value.service == "test_svc"


@pytest.mark.asyncio
async def test_circuit_breaker_recovers_after_timeout():
    """Circuit transitions to half-open after recovery timeout, then closes on success."""
    breaker = CircuitBreaker("test_svc", failure_threshold=2, recovery_timeout=0.1)

    async def fail():
        raise ConnectionError("down")

    # Trip the breaker
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
    assert breaker.state == "open"

    # Wait for recovery timeout
    import asyncio
    await asyncio.sleep(0.15)

    assert breaker.state == "half_open"

    # Successful call closes the circuit
    async def ok():
        return "recovered"

    result = await breaker.call(ok)
    assert result == "recovered"
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_success_resets_failure_count():
    """A success after partial failures resets the counter."""
    breaker = CircuitBreaker("test_svc", failure_threshold=5, recovery_timeout=60)

    async def fail():
        raise ConnectionError("down")

    async def ok():
        return "ok"

    # 3 failures (below threshold)
    for _ in range(3):
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
    assert breaker.failure_count == 3

    # Success resets
    await breaker.call(ok)
    assert breaker.failure_count == 0
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_circuit_breaker_to_dict():
    """to_dict exports state for metrics."""
    breaker = CircuitBreaker("easypost", failure_threshold=5, recovery_timeout=60)
    d = breaker.to_dict()
    assert d["service"] == "easypost"
    assert d["state"] == "closed"
    assert d["failure_count"] == 0
    assert d["failure_threshold"] == 5
    assert d["recovery_timeout"] == 60


@pytest.mark.asyncio
async def test_circuit_breaker_reset():
    """Manual reset closes the circuit."""
    breaker = CircuitBreaker("test_svc", failure_threshold=2, recovery_timeout=60)

    async def fail():
        raise ConnectionError("down")

    for _ in range(2):
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
    assert breaker.state == "open"

    breaker.reset()
    assert breaker.state == "closed"
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_easypost_breaker_instance_exists():
    """The easypost_breaker is properly configured."""
    assert easypost_breaker.service_name == "easypost"
    assert easypost_breaker.failure_threshold == 5
    # Reset it in case other tests tripped it
    easypost_breaker.reset()
