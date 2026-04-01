from __future__ import annotations

import logging

from pdf_converter_bot.bot_app import PDFConverterBot
from pdf_converter_bot.config import load_settings
from pdf_converter_bot.providers import ILovePDFProvider


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Prevent HTTP client request-line logs from exposing bot token in URL.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    configure_logging()
    settings = load_settings()
    provider = ILovePDFProvider(
        public_key=settings.ilovepdf_public_key,
        secret_key=settings.ilovepdf_secret_key,
        timeout_seconds=settings.conversion_timeout_seconds,
    )

    app = PDFConverterBot(settings=settings, provider=provider).build_application()
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
