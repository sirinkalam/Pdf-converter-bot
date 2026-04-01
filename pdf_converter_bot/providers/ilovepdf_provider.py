from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path
from typing import Any, Callable

import httpx

from ..errors import ProviderExecutionError, ProviderTimeoutError
from ..validation import choose_ilovepdf_tool

AUTH_URL = "https://api.ilovepdf.com/v1/auth"
START_URL_TEMPLATE = "https://api.ilovepdf.com/v1/start/{tool}/{region}"
UPLOAD_URL_TEMPLATE = "https://{server}/v1/upload"
PROCESS_URL_TEMPLATE = "https://{server}/v1/process"
DOWNLOAD_URL_TEMPLATE = "https://{server}/v1/download/{task}"
DELETE_TASK_URL_TEMPLATE = "https://{server}/v1/task/{task}"


class ILovePDFProvider:
    def __init__(
        self,
        public_key: str,
        secret_key: str,
        timeout_seconds: int = 120,
        region: str = "us",
        http_client_factory: Callable[..., Any] = httpx.AsyncClient,
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.timeout_seconds = timeout_seconds
        self.region = region
        self.http_client_factory = http_client_factory

    async def convert_to_pdf(self, input_path: Path, extension: str, mime_type: str | None) -> Path:
        try:
            return await asyncio.wait_for(
                self._convert_internal(input_path, extension, mime_type),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError("Conversion timed out.") from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Conversion timed out.") from exc
        except ProviderExecutionError:
            raise
        except Exception as exc:
            raise ProviderExecutionError("Conversion provider failed.") from exc

    async def _convert_internal(self, input_path: Path, extension: str, mime_type: str | None) -> Path:
        tool = choose_ilovepdf_tool(extension)
        task_id: str | None = None
        server: str | None = None

        async with self.http_client_factory(timeout=self.timeout_seconds) as client:
            token = await self._authenticate(client)
            headers = {"Authorization": f"Bearer {token}"}

            start_payload = await self._start_task(client, headers, tool)
            task_id = str(start_payload.get("task", ""))
            server = str(start_payload.get("server", ""))
            if not task_id or not server:
                raise ProviderExecutionError("Invalid start-task response from iLovePDF.")

            try:
                upload_payload = await self._upload_file(
                    client=client,
                    headers=headers,
                    server=server,
                    task_id=task_id,
                    input_path=input_path,
                    mime_type=mime_type,
                )
                server_filename = str(upload_payload.get("server_filename", ""))
                if not server_filename:
                    raise ProviderExecutionError("Upload step did not return server filename.")

                await self._process_task(
                    client=client,
                    headers=headers,
                    server=server,
                    task_id=task_id,
                    tool=tool,
                    server_filename=server_filename,
                    original_filename=input_path.name,
                )
                content, content_type = await self._download_task(
                    client=client,
                    headers=headers,
                    server=server,
                    task_id=task_id,
                )
            finally:
                await self._delete_task(client, headers, server, task_id)

        output_path = input_path.with_suffix(".pdf")
        output_bytes = self._extract_pdf_bytes(content, content_type)
        output_path.write_bytes(output_bytes)
        return output_path

    async def _authenticate(self, client: Any) -> str:
        response = await client.post(AUTH_URL, data={"public_key": self.public_key})
        payload = self._ensure_success_json(response)
        token = str(payload.get("token", "")).strip()
        if not token:
            raise ProviderExecutionError("Authentication token missing in iLovePDF response.")
        return token

    async def _start_task(self, client: Any, headers: dict[str, str], tool: str) -> dict[str, Any]:
        url = START_URL_TEMPLATE.format(tool=tool, region=self.region)
        response = await client.get(url, headers=headers)
        return self._ensure_success_json(response)

    async def _upload_file(
        self,
        client: Any,
        headers: dict[str, str],
        server: str,
        task_id: str,
        input_path: Path,
        mime_type: str | None,
    ) -> dict[str, Any]:
        url = UPLOAD_URL_TEMPLATE.format(server=server)
        media_type = mime_type or "application/octet-stream"
        with input_path.open("rb") as fh:
            response = await client.post(
                url,
                headers=headers,
                data={"task": task_id},
                files={"file": (input_path.name, fh, media_type)},
            )
        return self._ensure_success_json(response)

    async def _process_task(
        self,
        client: Any,
        headers: dict[str, str],
        server: str,
        task_id: str,
        tool: str,
        server_filename: str,
        original_filename: str,
    ) -> None:
        url = PROCESS_URL_TEMPLATE.format(server=server)
        payload = {
            "task": task_id,
            "tool": tool,
            "files": [
                {
                    "server_filename": server_filename,
                    "filename": original_filename,
                }
            ],
        }
        response = await client.post(url, headers=headers, json=payload)
        self._ensure_success_json(response)

    async def _download_task(
        self,
        client: Any,
        headers: dict[str, str],
        server: str,
        task_id: str,
    ) -> tuple[bytes, str]:
        url = DOWNLOAD_URL_TEMPLATE.format(server=server, task=task_id)
        response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            raise ProviderExecutionError(self._build_error_message(response))

        content_type = response.headers.get("Content-Type", "")
        return response.content, content_type

    async def _delete_task(
        self,
        client: Any,
        headers: dict[str, str],
        server: str | None,
        task_id: str | None,
    ) -> None:
        if not server or not task_id:
            return

        url = DELETE_TASK_URL_TEMPLATE.format(server=server, task=task_id)
        try:
            await client.delete(url, headers=headers, params={"secret_key": self.secret_key})
        except Exception:
            return

    @staticmethod
    def _extract_pdf_bytes(content: bytes, content_type: str) -> bytes:
        lower_content_type = content_type.lower()
        if "zip" in lower_content_type or zipfile.is_zipfile(io.BytesIO(content)):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = zf.namelist()
                if not names:
                    raise ProviderExecutionError("Downloaded ZIP has no files.")
                pdf_names = [name for name in names if name.lower().endswith(".pdf")]
                target = pdf_names[0] if pdf_names else names[0]
                return zf.read(target)

        return content

    def _ensure_success_json(self, response: Any) -> dict[str, Any]:
        if response.status_code >= 400:
            raise ProviderExecutionError(self._build_error_message(response))

        try:
            payload = response.json()
        except Exception as exc:
            raise ProviderExecutionError("Invalid JSON response from iLovePDF.") from exc

        if not isinstance(payload, dict):
            raise ProviderExecutionError("Unexpected iLovePDF response shape.")
        return payload

    @staticmethod
    def _build_error_message(response: Any) -> str:
        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                message = error_obj.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        return f"iLovePDF API request failed with status {response.status_code}."
