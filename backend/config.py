"""Application settings loaded from environment variables."""

import os
from pathlib import Path


class Settings:
    """Simple settings container reading from environment variables."""

    def __init__(self):
        self.ENV: str = os.environ.get("ENV", "dev")
        self.SECRET_KEY: str = os.environ.get(
            "SECRET_KEY", "dev-secret-key-change-in-production"
        )
        self.DATABASE_PATH: str = os.environ.get(
            "DATABASE_PATH", "backend/data/strype.db"
        )
        self.DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")
        self.FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "")

        # Stripe billing
        self.STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
        self.STRIPE_PRICE_ID: str = os.environ.get("STRIPE_PRICE_ID", "")
        self.STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        # Admin
        self.ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")

        # Email (SendGrid)
        self.SENDGRID_API_KEY: str = os.environ.get("SENDGRID_API_KEY", "")
        self.FROM_EMAIL: str = os.environ.get("FROM_EMAIL", "")

        # Stripe Robot plan
        self.STRIPE_ROBOT_PRICE_ID: str = os.environ.get("STRIPE_ROBOT_PRICE_ID", "")

        # Shipping (EasyPost)
        self.EASYPOST_API_KEY: str = os.environ.get("EASYPOST_API_KEY", "")
        self.SHIP_FROM_ADDRESS: dict = {
            "name": "Strype Robotics",
            "street1": os.environ.get("SHIP_FROM_STREET", ""),
            "city": os.environ.get("SHIP_FROM_CITY", ""),
            "state": os.environ.get("SHIP_FROM_STATE", ""),
            "zip": os.environ.get("SHIP_FROM_ZIP", ""),
            "country": "US",
        }

        # Token refresh
        self.REFRESH_TOKEN_EXPIRE_DAYS: int = int(
            os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )

        # Organization / storage foundations
        self.MEDIA_STORAGE_PATH: str = os.environ.get(
            "MEDIA_STORAGE_PATH", "backend/data/media"
        )
        self.OBJECT_STORAGE_BACKEND: str = os.environ.get(
            "OBJECT_STORAGE_BACKEND", "local"
        )
        self.S3_BUCKET: str = os.environ.get("S3_BUCKET", "")
        self.S3_PRIVATE_BUCKET: str = os.environ.get("S3_PRIVATE_BUCKET", self.S3_BUCKET)
        self.S3_REPORTS_BUCKET: str = os.environ.get("S3_REPORTS_BUCKET", self.S3_PRIVATE_BUCKET)
        self.S3_ENDPOINT_URL: str = os.environ.get("S3_ENDPOINT_URL", "")
        self.S3_REGION: str = os.environ.get("S3_REGION", "")
        self.S3_ACCESS_KEY_ID: str = os.environ.get("S3_ACCESS_KEY_ID", "")
        self.S3_SECRET_ACCESS_KEY: str = os.environ.get("S3_SECRET_ACCESS_KEY", "")
        self.AWS_REGION: str = os.environ.get("AWS_REGION", self.S3_REGION or "us-east-1")
        self.SECRETS_MANAGER_PREFIX: str = os.environ.get("SECRETS_MANAGER_PREFIX", "")
        self.SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
        self.MAX_UPLOAD_BYTES: int = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

        # Robot deposit (0 = no deposit)
        self.ROBOT_DEPOSIT: float = float(os.environ.get("ROBOT_DEPOSIT", "0"))

        # Plan limits
        self.PLAN_LIMITS: dict = {
            "free": {"max_lots": 1, "max_jobs": 5, "robots": 0},
            "pro": {"max_lots": 999, "max_jobs": 999, "robots": 0},
            "robot": {"max_lots": 999, "max_jobs": 999, "robots": 1},
            "enterprise": {"max_lots": 999, "max_jobs": 999, "robots": 10},
        }

    def resolved_database_url(self) -> str:
        """Return the canonical database URL for the runtime."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        path = Path(self.DATABASE_PATH).resolve().as_posix()
        return f"sqlite+aiosqlite:///{path}"


    def validate(self):
        """Validate configuration at startup. Raises in production for insecure defaults."""
        import logging
        log = logging.getLogger("strype")
        if self.ENV != "dev":
            if self.SECRET_KEY == "dev-secret-key-change-in-production":
                raise RuntimeError(
                    "FATAL: SECRET_KEY is using the default value. "
                    "Set a secure random key via the SECRET_KEY environment variable."
                )
            if self.CORS_ORIGINS.strip() == "*":
                raise RuntimeError(
                    "FATAL: CORS_ORIGINS is set to wildcard '*' in production. "
                    "Set specific origins via the CORS_ORIGINS environment variable."
                )
            if not self.DATABASE_URL and self.DATABASE_PATH:
                log.warning("DATABASE_URL is not set - production will fall back to DATABASE_PATH")
        else:
            if self.SECRET_KEY == "dev-secret-key-change-in-production":
                log.warning("SECRET_KEY is using the default value — set a secure key for production")
            if self.CORS_ORIGINS.strip() == "*":
                log.warning("CORS_ORIGINS is set to wildcard '*' — restrict in production")
        if not self.STRIPE_WEBHOOK_SECRET and self.STRIPE_SECRET_KEY:
            log.warning("STRIPE_WEBHOOK_SECRET is not set — webhook verification will fail")


settings = Settings()
settings.validate()
