"""Lightweight async circuit breaker for external API calls.

Prevents cascading failures when external services (EasyPost, SendGrid, Stripe)
are down. After N consecutive failures, the circuit opens for M seconds and
fails fast without making HTTP calls. After the timeout, one trial call is
allowed (half-open). On success, the circuit closes.

Usage:
    breaker = CircuitBreaker("easypost", failure_threshold=5, recovery_timeout=60)

    try:
        result = await breaker.call(some_async_function, arg1, arg2)
    except CircuitOpenError:
        # Service is down, fail fast
        ...
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger("strype.circuit_breaker")


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Circuit open for {service} — retry in {retry_after:.0f}s")


class CircuitBreaker:
    """Per-service async circuit breaker with closed → open → half-open states."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._state: str = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        """Current circuit state, auto-transitioning from open → half_open after timeout."""
        if self._state == "open":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def _record_success(self) -> None:
        self._failure_count = 0
        if self._state != "closed":
            logger.info("Circuit %s: CLOSED (recovered)", self.service_name)
        self._state = "closed"

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                "Circuit %s: OPEN after %d consecutive failures (retry in %ds)",
                self.service_name,
                self._failure_count,
                self.recovery_timeout,
            )

    async def call(self, fn: Callable[..., Coroutine], *args: Any, **kwargs: Any) -> Any:
        """Execute fn through the circuit breaker.

        Raises CircuitOpenError if the circuit is open and the recovery timeout
        has not elapsed. In half-open state, allows one trial call.
        """
        current_state = self.state

        if current_state == "open":
            retry_after = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
            raise CircuitOpenError(self.service_name, max(0, retry_after))

        try:
            result = await fn(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure()
            raise

    def reset(self) -> None:
        """Manually reset the circuit to closed state."""
        self._failure_count = 0
        self._state = "closed"

    def to_dict(self) -> dict:
        """Export state for metrics/health endpoints."""
        return {
            "service": self.service_name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
