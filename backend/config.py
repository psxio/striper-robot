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


settings = Settings()
