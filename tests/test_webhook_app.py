
import pytest
from fastapi import HTTPException

from pdf_converter_bot.config import Settings
from pdf_converter_bot.webhook_app import process_webhook_payload, telegram_webhook
import pdf_converter_bot.webhook_app as webhook_module


class DummyTelegramApp:
    def __init__(self) -> None:
        self.bot = object()
        self.processed_update_id: int | None = None

    async def process_update(self, update) -> None:
        self.processed_update_id = update.update_id


class FakeRequest:
    def __init__(self, payload, headers=None, raise_json: bool = False) -> None:
        self._payload = payload
        self.headers = headers or {}
        self._raise_json = raise_json

    async def json(self):
        if self._raise_json:
            raise ValueError("bad json")
        return self._payload


@pytest.mark.asyncio
async def test_process_webhook_payload_processes_update() -> None:
    app = DummyTelegramApp()
    await process_webhook_payload({"update_id": 12345}, app)
    assert app.processed_update_id == 12345


@pytest.mark.asyncio
async def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    settings = Settings(
        telegram_bot_token="token",
        ilovepdf_public_key="pk",
        ilovepdf_secret_key="sk",
        telegram_webhook_secret="expected-secret",
    )

    monkeypatch.setattr(webhook_module, "get_settings", lambda: settings)

    async def fake_get_application():
        return DummyTelegramApp()

    monkeypatch.setattr(webhook_module, "get_telegram_application", fake_get_application)

    request = FakeRequest(payload={"update_id": 1}, headers={"x-telegram-bot-api-secret-token": "bad-secret"})

    with pytest.raises(HTTPException) as exc:
        await telegram_webhook(request)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_returns_ok(monkeypatch) -> None:
    settings = Settings(
        telegram_bot_token="token",
        ilovepdf_public_key="pk",
        ilovepdf_secret_key="sk",
        telegram_webhook_secret="expected-secret",
    )

    monkeypatch.setattr(webhook_module, "get_settings", lambda: settings)

    async def fake_get_application():
        return DummyTelegramApp()

    called = {"seen": False}

    async def fake_process(payload, application):
        called["seen"] = True
        assert payload["update_id"] == 7
        assert isinstance(application, DummyTelegramApp)

    monkeypatch.setattr(webhook_module, "get_telegram_application", fake_get_application)
    monkeypatch.setattr(webhook_module, "process_webhook_payload", fake_process)

    request = FakeRequest(
        payload={"update_id": 7},
        headers={"x-telegram-bot-api-secret-token": "expected-secret"},
    )

    response = await telegram_webhook(request)

    assert response == {"ok": True}
    assert called["seen"]


@pytest.mark.asyncio
async def test_telegram_webhook_rejects_bad_json(monkeypatch) -> None:
    settings = Settings(
        telegram_bot_token="token",
        ilovepdf_public_key="pk",
        ilovepdf_secret_key="sk",
    )

    monkeypatch.setattr(webhook_module, "get_settings", lambda: settings)

    request = FakeRequest(payload=None, raise_json=True)

    with pytest.raises(HTTPException) as exc:
        await telegram_webhook(request)

    assert exc.value.status_code == 400
