"""Rate limiting configuration using slowapi with per-plan dynamic limits."""

import base64
import json
import os

from starlette.requests import Request
from slowapi import Limiter

from .config import settings

# Number of trusted reverse proxies in front of the app (e.g. nginx, Railway).
# The real client IP is this many positions from the right in X-Forwarded-For.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))


def _get_real_address(request: Request) -> str:
    """Extract client IP, using the rightmost trusted entry in X-Forwarded-For.

    The leftmost IP is client-controlled and can be spoofed. The rightmost IP
    was added by the nearest trusted proxy and reflects the actual connecting
    client.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",")]
        # Pick the IP that is TRUSTED_PROXY_COUNT positions from the right
        idx = max(0, len(ips) - TRUSTED_PROXY_COUNT)
        return ips[idx]
    if request.client:
        return request.client.host
    return "127.0.0.1"


def _get_plan_from_request(request: Request) -> str:
    """Extract the user's plan from the JWT without full verification.

    This is a fast-path for rate limiting only — reads the JWT payload via
    base64 decode without cryptographic verification. Full auth verification
    still happens in get_current_user(). Returns 'default' if no valid token.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "default"
    token = auth.split(" ", 1)[1]
    try:
        # JWT is header.payload.signature — decode the payload segment
        parts = token.split(".")
        if len(parts) != 3:
            return "default"
        # Add padding for base64
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("plan", "default")
    except Exception:
        return "default"


def _plan_rate_limit(request: Request) -> str:
    """Return the rate limit string for the requesting user's plan."""
    plan = _get_plan_from_request(request)
    return settings.RATE_LIMITS.get(plan, settings.RATE_LIMITS["default"])


limiter = Limiter(key_func=_get_real_address, default_limits=[_plan_rate_limit])
