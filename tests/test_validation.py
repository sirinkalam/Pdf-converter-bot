from pdf_converter_bot.errors import FileTooLargeError, UnsupportedFileError
from pdf_converter_bot.validation import choose_ilovepdf_tool, validate_file


def test_validate_file_accepts_supported_extension() -> None:
    ext = validate_file("report.DOCX", size_bytes=1024, max_file_mb=20)
    assert ext == "docx"


def test_validate_file_rejects_unsupported_extension() -> None:
    try:
        validate_file("archive.zip", size_bytes=1024, max_file_mb=20)
        raise AssertionError("Expected UnsupportedFileError")
    except UnsupportedFileError:
        pass


def test_validate_file_rejects_oversized_file() -> None:
    try:
        validate_file("book.txt", size_bytes=25 * 1024 * 1024, max_file_mb=20)
        raise AssertionError("Expected FileTooLargeError")
    except FileTooLargeError:
        pass


def test_choose_ilovepdf_tool() -> None:
    assert choose_ilovepdf_tool("jpg") == "imagepdf"
    assert choose_ilovepdf_tool("docx") == "officepdf"
