from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ilovepdf_public_key: str
    ilovepdf_secret_key: str
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    max_file_mb: int = 20
    max_concurrent_jobs: int = 2
    conversion_timeout_seconds: int = 120
    daily_conversions_per_user: int = 20


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    public_key = os.getenv("ILOVEPDF_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("ILOVEPDF_SECRET_KEY", "").strip()
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    max_file_mb = int(os.getenv("MAX_FILE_MB", "20"))
    max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    conversion_timeout_seconds = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", "120"))
    daily_conversions_per_user = int(os.getenv("DAILY_CONVERSIONS_PER_USER", "20"))

    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("ILOVEPDF_PUBLIC_KEY", public_key),
            ("ILOVEPDF_SECRET_KEY", secret_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        telegram_bot_token=token,
        ilovepdf_public_key=public_key,
        ilovepdf_secret_key=secret_key,
        telegram_webhook_url=webhook_url,
        telegram_webhook_secret=webhook_secret,
        max_file_mb=max_file_mb,
        max_concurrent_jobs=max_concurrent_jobs,
        conversion_timeout_seconds=conversion_timeout_seconds,
        daily_conversions_per_user=daily_conversions_per_user,
    )
