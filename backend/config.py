"""Application settings loaded from environment variables."""

import os


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
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )
        self.CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")
        self.FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "")

        # Stripe billing
        self.STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
        self.STRIPE_PRICE_ID: str = os.environ.get("STRIPE_PRICE_ID", "")
        self.STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        # Admin
        self.ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")

        # Plan limits
        self.PLAN_LIMITS: dict = {
            "free": {"max_lots": 1, "max_jobs": 5},
            "pro": {"max_lots": 999, "max_jobs": 999},
        }


    def validate(self):
        """Warn about insecure defaults at startup."""
        import logging
        log = logging.getLogger("strype")
        if self.SECRET_KEY == "dev-secret-key-change-in-production" and self.ENV != "dev":
            log.warning("SECRET_KEY is using the default value — set a secure key for production")
        if self.CORS_ORIGINS.strip() == "*" and self.ENV != "dev":
            log.warning("CORS_ORIGINS is set to wildcard '*' — restrict in production")
        if not self.STRIPE_WEBHOOK_SECRET and self.STRIPE_SECRET_KEY:
            log.warning("STRIPE_WEBHOOK_SECRET is not set — webhook verification will fail")


settings = Settings()
settings.validate()
