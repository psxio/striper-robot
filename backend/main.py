"""FastAPI entry point for the Strype Cloud Platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import init_db, get_db
from .rate_limit import limiter
from .routers import auth_router, lots_router, jobs_router, waitlist_router, user_router, billing_router, admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("strype")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Strype Cloud Platform starting up (env=%s)", settings.ENV)
    await init_db()
    yield


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
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/api/health")
async def health():
    """Health check with DB connectivity test."""
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
        return {"status": "ok", "version": "0.3.0"}
    except Exception:
        return Response(
            content='{"status":"error","version":"0.3.0"}',
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

# Serve frontend -- must be LAST (catch-all)
app.mount("/", StaticFiles(directory="site", html=True), name="site")
