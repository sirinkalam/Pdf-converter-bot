from pdf_converter_bot.bot_app import PDFConverterBot
from pdf_converter_bot.config import Settings
from pdf_converter_bot.errors import (
    FileTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    UnsupportedFileError,
)


class DummyProvider:
    async def convert_to_pdf(self, input_path, extension, mime_type):
        raise NotImplementedError


def make_bot() -> PDFConverterBot:
    settings = Settings(
        telegram_bot_token="token",
        ilovepdf_public_key="pk",
        ilovepdf_secret_key="sk",
    )
    return PDFConverterBot(settings=settings, provider=DummyProvider())


def test_user_message_mapping() -> None:
    bot = make_bot()

    assert "Unsupported" in bot._user_message_for_error(UnsupportedFileError("x"))
    assert "20" in bot._user_message_for_error(FileTooLargeError("File exceeds 20 MB size limit."))
    assert "timed out" in bot._user_message_for_error(ProviderTimeoutError("x"))
    assert "provider failed" in bot._user_message_for_error(ProviderExecutionError("x"))
