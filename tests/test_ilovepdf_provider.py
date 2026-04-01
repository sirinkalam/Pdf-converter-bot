from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pdf_converter_bot.errors import ProviderExecutionError, ProviderTimeoutError
from pdf_converter_bot.providers.ilovepdf_provider import ILovePDFProvider


class FakeResponse:
    def __init__(self, status_code: int, payload=None, content: bytes = b"", headers=None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeClient:
    def __init__(self, scripted: list[tuple[str, FakeResponse]], timeout: int = 120) -> None:
        self.scripted = scripted
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, **_kwargs):
        return self._next("POST", url)

    async def get(self, url: str, **_kwargs):
        return self._next("GET", url)

    async def delete(self, url: str, **_kwargs):
        return self._next("DELETE", url)

    def _next(self, expected_method: str, expected_url: str) -> FakeResponse:
        if not self.scripted:
            raise AssertionError("No scripted response left")
        method, response = self.scripted.pop(0)
        if method != expected_method:
            raise AssertionError(f"Expected method {method} but got {expected_method}")
        return response


@pytest.mark.asyncio
async def test_convert_to_pdf_success(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.docx"
    input_path.write_text("hello", encoding="utf-8")

    scripted = [
        ("POST", FakeResponse(200, {"token": "abc"})),
        ("GET", FakeResponse(200, {"server": "api11.ilovepdf.com", "task": "task-1"})),
        ("POST", FakeResponse(200, {"server_filename": "remote-file-1"})),
        ("POST", FakeResponse(200, {"status": "TaskSuccess"})),
        ("GET", FakeResponse(200, content=b"%PDF-1.4\n", headers={"Content-Type": "application/pdf"})),
        ("DELETE", FakeResponse(200, {"status": "TaskDeleted"})),
    ]

    provider = ILovePDFProvider(
        public_key="pk",
        secret_key="sk",
        timeout_seconds=3,
        http_client_factory=lambda **kwargs: FakeClient(scripted=scripted, **kwargs),
    )

    output = await provider.convert_to_pdf(input_path, "docx", "application/vnd.openxmlformats")
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")


@pytest.mark.asyncio
async def test_convert_to_pdf_provider_error(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.docx"
    input_path.write_text("hello", encoding="utf-8")

    scripted = [
        ("POST", FakeResponse(200, {"token": "abc"})),
        ("GET", FakeResponse(200, {"server": "api11.ilovepdf.com", "task": "task-1"})),
        (
            "POST",
            FakeResponse(
                400,
                {"error": {"message": "Unsupported input file."}},
            ),
        ),
        ("DELETE", FakeResponse(200, {"status": "TaskDeleted"})),
    ]

    provider = ILovePDFProvider(
        public_key="pk",
        secret_key="sk",
        timeout_seconds=3,
        http_client_factory=lambda **kwargs: FakeClient(scripted=scripted, **kwargs),
    )

    with pytest.raises(ProviderExecutionError):
        await provider.convert_to_pdf(input_path, "docx", "application/vnd.openxmlformats")


@pytest.mark.asyncio
async def test_convert_to_pdf_timeout(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.docx"
    input_path.write_text("hello", encoding="utf-8")

    class SlowClient:
        def __init__(self, timeout: int = 120) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **_kwargs):
            await asyncio.sleep(0.2)
            return FakeResponse(200, {"token": "abc"})

        async def get(self, url: str, **_kwargs):
            return FakeResponse(200, {"server": "api11.ilovepdf.com", "task": "task-1"})

        async def delete(self, url: str, **_kwargs):
            return FakeResponse(200, {"status": "TaskDeleted"})

    provider = ILovePDFProvider(
        public_key="pk",
        secret_key="sk",
        timeout_seconds=0.01,
        http_client_factory=lambda **kwargs: SlowClient(**kwargs),
    )

    with pytest.raises(ProviderTimeoutError):
        await provider.convert_to_pdf(input_path, "docx", "application/vnd.openxmlformats")
