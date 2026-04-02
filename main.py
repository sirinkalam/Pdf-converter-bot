from __future__ import annotations

import argparse
import json
import logging

import httpx

from pdf_converter_bot.config import load_settings


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _telegram_api_url(bot_token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{bot_token}/{method}"


def set_webhook() -> None:
    settings = load_settings()
    if not settings.telegram_webhook_url:
        raise ValueError("Set TELEGRAM_WEBHOOK_URL before calling set-webhook.")

    payload = {"url": settings.telegram_webhook_url}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    with httpx.Client(timeout=30) as client:
        response = client.post(_telegram_api_url(settings.telegram_bot_token, "setWebhook"), json=payload)
        response.raise_for_status()
        body = response.json()

    if not body.get("ok"):
        raise RuntimeError(f"Telegram setWebhook failed: {body}")

    print("Webhook set successfully")
    print(json.dumps(body, indent=2))


def webhook_info() -> None:
    settings = load_settings()
    with httpx.Client(timeout=30) as client:
        response = client.get(_telegram_api_url(settings.telegram_bot_token, "getWebhookInfo"))
        response.raise_for_status()
        body = response.json()

    print(json.dumps(body, indent=2))


def delete_webhook() -> None:
    settings = load_settings()
    with httpx.Client(timeout=30) as client:
        response = client.post(_telegram_api_url(settings.telegram_bot_token, "deleteWebhook"))
        response.raise_for_status()
        body = response.json()

    if not body.get("ok"):
        raise RuntimeError(f"Telegram deleteWebhook failed: {body}")

    print("Webhook deleted")
    print(json.dumps(body, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram webhook utility")
    parser.add_argument(
        "command",
        choices=("set-webhook", "webhook-info", "delete-webhook"),
        help="Webhook command to run",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()

    if args.command == "set-webhook":
        set_webhook()
    elif args.command == "webhook-info":
        webhook_info()
    else:
        delete_webhook()


if __name__ == "__main__":
    main()
