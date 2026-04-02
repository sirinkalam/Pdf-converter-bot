from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from telegram import Update
from telegram.ext import Application

from .bot_app import PDFConverterBot
from .config import Settings, load_settings
from .providers import ILovePDFProvider

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="PDF Converter Bot Webhook")

_app_lock = asyncio.Lock()
_telegram_application: Application | None = None
_settings: Settings | None = None


async def get_telegram_application() -> Application:
    global _telegram_application
    global _settings

    if _telegram_application is not None:
        return _telegram_application

    async with _app_lock:
        if _telegram_application is None:
            _settings = load_settings()
            provider = ILovePDFProvider(
                public_key=_settings.ilovepdf_public_key,
                secret_key=_settings.ilovepdf_secret_key,
                timeout_seconds=_settings.conversion_timeout_seconds,
            )
            bot = PDFConverterBot(settings=_settings, provider=provider)
            application = bot.build_application(enable_updater=False)
            await application.initialize()
            _telegram_application = application
            LOGGER.info("Webhook application initialized")

    return _telegram_application


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


async def process_webhook_payload(payload: dict[str, Any], application: Application) -> None:
    update = Update.de_json(payload, application.bot)
    if update is None:
        return
    await application.process_update(update)


@app.get("/")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/")
async def telegram_webhook(request: Request) -> dict[str, bool]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    settings = get_settings()
    if settings.telegram_webhook_secret:
        provided_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if provided_secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Forbidden")

    application = await get_telegram_application()
    await process_webhook_payload(payload, application)
    return {"ok": True}
