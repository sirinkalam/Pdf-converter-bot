from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def create_job_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="pdfbot_"))


def cleanup_job_files(job_dir: Path) -> None:
    shutil.rmtree(job_dir, ignore_errors=True)
