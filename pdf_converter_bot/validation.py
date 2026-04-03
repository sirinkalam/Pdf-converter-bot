from __future__ import annotations

from pathlib import Path

from .errors import FileTooLargeError, UnsupportedFileError

SUPPORTED_EXTENSIONS = {
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "jpg",
    "jpeg",
    "png",
    "tiff",
    "odt",
    "rtf",
    "txt",
    "pdf",
}

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "tiff"}


def normalize_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower().strip()
    return suffix[1:] if suffix.startswith(".") else suffix


def sanitize_filename(filename: str, default_name: str = "upload.bin") -> str:
    clean_name = Path(filename or default_name).name
    return clean_name or default_name


def validate_file(filename: str, size_bytes: int, max_file_mb: int) -> str:
    ext = normalize_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError("Unsupported file format.")

    max_bytes = max_file_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeError(f"File exceeds {max_file_mb} MB size limit.")

    return ext


def choose_ilovepdf_tool(extension: str) -> str:
    return "imagepdf" if extension in IMAGE_EXTENSIONS else "officepdf"
