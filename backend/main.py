"""FastAPI entry point for the Strype Cloud Platform."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import init_db, get_db
from .rate_limit import limiter
from .routers import (
    auth_router, lots_router, jobs_router, waitlist_router, user_router,
    billing_router, admin_router, robot_router, schedule_router,
    estimate_router, telemetry_router,
)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Strype Cloud Platform starting up (env=%s)", settings.ENV)
    await init_db()
    # Start background scheduler (skip in test)
    scheduler_task = None
    if settings.ENV != "test":
        from .services.scheduler import run_scheduler_loop
        scheduler_task = asyncio.create_task(run_scheduler_loop())
    yield
    if scheduler_task:
        scheduler_task.cancel()
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
async def csrf_protection(request: Request, call_next):
    """CSRF double-submit validation for refresh-cookie auth."""
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and request.url.path == "/api/auth/refresh"
        and "Authorization" not in request.headers
    ):
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        if csrf_cookie and csrf_header != csrf_cookie:
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
        )

    return response


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
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://api.stripe.com; "
        "frame-src https://js.stripe.com; "
        "font-src 'self'"
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
        return {"status": "ok", "version": "0.5.0"}
    except Exception:
        return Response(
            content='{"status":"error","version":"0.5.0"}',
            status_code=503,
            media_type="application/json",
        )


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

# Serve frontend -- must be LAST (catch-all)
app.mount("/", StaticFiles(directory="site", html=True), name="site")
