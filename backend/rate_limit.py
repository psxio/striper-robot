"""Rate limiting configuration using slowapi."""

from starlette.requests import Request
from slowapi import Limiter


def _get_real_address(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the real client
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


limiter = Limiter(key_func=_get_real_address, default_limits=["100/minute"])
