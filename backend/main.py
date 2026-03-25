"""FastAPI entry point for the Strype Cloud Platform."""

import asyncio
import json
import logging
import uuid as _uuid
from pathlib import Path

__version__ = "0.5.2"
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import init_db, get_db
from .metrics import record_request, format_prometheus
from .rate_limit import limiter

# Telemetry retention: keep 7 days of data by default
TELEMETRY_RETENTION_DAYS = 7
from .routers import (
    auth_router, lots_router, jobs_router, waitlist_router, user_router,
    billing_router, admin_router, robot_router, schedule_router,
    estimate_router, telemetry_router, organization_router, sites_router,
    quotes_router, operations_router, reporting_router, fleet_router, cloud_router,
    robot_claim_router,
)
from .services import storage_service

if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration()],
            environment=settings.ENV,
            release=__version__,
            traces_sample_rate=0.0,
        )
    except ImportError:
        logging.getLogger("strype").warning("sentry-sdk is not installed; Sentry disabled")


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record):
        log = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, default=str)


if settings.ENV != "dev":
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

logger = logging.getLogger("strype")


async def _blocklist_cleanup_loop() -> None:
    """Purge expired JWT blocklist entries and old telemetry every 24 hours."""
    while True:
        try:
            await asyncio.sleep(86400)  # 24 h
            now = datetime.now(timezone.utc).isoformat()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=TELEMETRY_RETENTION_DAYS)).isoformat()
            async for db in get_db():
                await db.execute("DELETE FROM token_blocklist WHERE expires_at < ?", (now,))
                result = await db.execute("DELETE FROM robot_telemetry WHERE created_at < ?", (cutoff,))
                await db.commit()
                break
            logger.info("Cleanup complete: blocklist purged, telemetry older than %d days removed", TELEMETRY_RETENTION_DAYS)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Cleanup loop failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Strype Cloud Platform starting up (env=%s)", settings.ENV)
    await init_db()
    storage_health = await storage_service.check_storage_health()
    logger.info("Storage backend ready: %s", storage_health["backend"])
    # Start background tasks (skip in test)
    scheduler_task = None
    blocklist_task = None
    if settings.ENV != "test":
        from .services.scheduler import run_scheduler_loop
        scheduler_task = asyncio.create_task(run_scheduler_loop())
        blocklist_task = asyncio.create_task(_blocklist_cleanup_loop())
    yield
    if scheduler_task:
        scheduler_task.cancel()
    if blocklist_task:
        blocklist_task.cancel()
    logger.info("Strype Cloud Platform shutting down gracefully")


app = FastAPI(title="Strype Cloud", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS from environment
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID for log correlation."""
    request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record request count and latency for Prometheus metrics."""
    import time as _time
    start = _time.monotonic()
    response = await call_next(request)
    duration = _time.monotonic() - start
    # Skip metrics and static file paths to reduce noise
    path = request.url.path
    if path.startswith("/api/") and path != "/api/metrics":
        record_request(request.method, path, response.status_code, duration)
    return response


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """CSRF double-submit validation for cookie-authenticated state-changing requests.

    Enforced when the request has a refresh_token cookie (i.e. an active session)
    and no Bearer token — this covers the /refresh endpoint and any future
    cookie-authed routes.  Public endpoints (register, login, forgot-password)
    and robot heartbeat (X-Robot-Key) are not affected.
    """
    # CSRF-exempt paths: auth login/register/forgot/reset are public forms,
    # webhook is server-to-server, heartbeat uses X-Robot-Key.
    _csrf_exempt = {
        "/api/auth/login", "/api/auth/register", "/api/auth/forgot-password",
        "/api/auth/reset-password", "/api/billing/webhook",
    }
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and "Authorization" not in request.headers
        and not request.headers.get("X-Robot-Key")
        and request.url.path not in _csrf_exempt
        and "refresh_token" in request.cookies
    ):
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or csrf_header != csrf_cookie:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed"},
            )

    response = await call_next(request)

    # Set CSRF cookie on responses if not already present
    if "csrf_token" not in request.cookies:
        import secrets
        response.set_cookie(
            "csrf_token",
            secrets.token_urlsafe(32),
            httponly=False,
            samesite="strict",
            secure=settings.ENV != "dev",
        )

    return response


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.MAX_UPLOAD_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body exceeds {settings.MAX_UPLOAD_BYTES} bytes"},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://api.stripe.com https://nominatim.openstreetmap.org; "
        "frame-src https://js.stripe.com; "
        "font-src 'self' https://fonts.gstatic.com"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions — return safe JSON, never leak stack traces."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health")
async def health():
    """Health check with DB connectivity test."""
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
        return {"status": "ok", "version": __version__}
    except Exception:
        return Response(
            content='{"status":"error","version":"' + __version__ + '"}',
            status_code=503,
            media_type="application/json",
        )


@app.get("/api/ready")
async def readiness():
    """Readiness check with DB, storage, and scheduler state."""
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
            break
        storage = await storage_service.check_storage_health()
        scheduler_health = {"running": False}
        if settings.ENV != "test":
            from .services.scheduler import get_scheduler_health

            scheduler_health = get_scheduler_health()
        return {
            "status": "ready",
            "version": __version__,
            "storage": storage,
            "scheduler": scheduler_health,
        }
    except Exception as exc:
        logger.exception("Readiness check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "version": __version__,
                "detail": str(exc) if settings.ENV in ("dev", "test") else "Readiness check failed",
            },
        )


@app.get("/api/metrics")
async def prometheus_metrics(request: Request):
    """Prometheus-compatible metrics endpoint.

    Protected by METRICS_TOKEN env var (Bearer auth) or admin JWT.
    """
    metrics_token = settings.METRICS_TOKEN
    if metrics_token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {metrics_token}":
            # Fall back to admin JWT check
            from .auth import get_admin_user
            try:
                await get_admin_user(request)
            except Exception:
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    else:
        # No METRICS_TOKEN set — require admin JWT
        from .auth import get_admin_user
        try:
            await get_admin_user(request)
        except Exception:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    return Response(content=format_prometheus(), media_type="text/plain; charset=utf-8")


app.include_router(auth_router.router)
app.include_router(lots_router.router)
app.include_router(jobs_router.router)
app.include_router(waitlist_router.router)
app.include_router(user_router.router)
app.include_router(billing_router.router)
app.include_router(admin_router.router)
app.include_router(robot_router.router)
app.include_router(schedule_router.router)
app.include_router(estimate_router.router)
app.include_router(telemetry_router.router)
app.include_router(organization_router.router)
app.include_router(sites_router.router)
app.include_router(quotes_router.router)
app.include_router(operations_router.router)
app.include_router(reporting_router.router)
app.include_router(fleet_router.router)
app.include_router(cloud_router.router)
app.include_router(robot_claim_router.router)

# Serve frontend -- must be LAST (catch-all)
site_dir = Path(__file__).resolve().parent.parent / "site"
app.mount("/", StaticFiles(directory=str(site_dir), html=True), name="site")
