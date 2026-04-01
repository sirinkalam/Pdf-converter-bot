from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PDFProvider(Protocol):
    async def convert_to_pdf(self, input_path: Path, extension: str, mime_type: str | None) -> Path:
        ...
