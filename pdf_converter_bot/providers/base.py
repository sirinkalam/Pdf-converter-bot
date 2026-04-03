from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PDFProvider(Protocol):
    async def convert_to_pdf(self, input_path: Path, extension: str, mime_type: str | None) -> Path:
        ...

    async def process_files(
        self,
        tool: str,
        inputs: list[tuple[Path, str | None]],
        output_basename: str,
        process_params: dict[str, Any] | None = None,
    ) -> Path:
        ...
