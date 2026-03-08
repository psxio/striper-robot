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

        # Robot deposit (0 = no deposit)
        self.ROBOT_DEPOSIT: float = float(os.environ.get("ROBOT_DEPOSIT", "0"))

        # Plan limits
        self.PLAN_LIMITS: dict = {
            "free": {"max_lots": 1, "max_jobs": 5, "robots": 0},
            "pro": {"max_lots": 999, "max_jobs": 999, "robots": 0},
            "robot": {"max_lots": 999, "max_jobs": 999, "robots": 1},
            "enterprise": {"max_lots": 999, "max_jobs": 999, "robots": 10},
        }


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
        else:
            if self.SECRET_KEY == "dev-secret-key-change-in-production":
                log.warning("SECRET_KEY is using the default value — set a secure key for production")
            if self.CORS_ORIGINS.strip() == "*":
                log.warning("CORS_ORIGINS is set to wildcard '*' — restrict in production")
        if not self.STRIPE_WEBHOOK_SECRET and self.STRIPE_SECRET_KEY:
            log.warning("STRIPE_WEBHOOK_SECRET is not set — webhook verification will fail")


settings = Settings()
settings.validate()
