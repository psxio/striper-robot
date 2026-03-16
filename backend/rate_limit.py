"""Rate limiting configuration using slowapi."""

import os

from starlette.requests import Request
from slowapi import Limiter

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


limiter = Limiter(key_func=_get_real_address, default_limits=["100/minute"])
