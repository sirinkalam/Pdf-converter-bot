from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from telegram import InputFile, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .errors import (
    ConversionError,
    FileTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    UnsupportedFileError,
)
from .providers.base import PDFProvider
from .rate_limit import DailyRateLimiter
from .storage import cleanup_job_files, create_job_dir
from .validation import sanitize_filename, validate_file

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomingUpload:
    file_id: str
    filename: str
    file_size: int
    mime_type: str | None


class PDFConverterBot:
    def __init__(self, settings: Settings, provider: PDFProvider) -> None:
        self.settings = settings
        self.provider = provider
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._rate_limiter = DailyRateLimiter(settings.daily_conversions_per_user)

    def build_application(self) -> Application:
        application = Application.builder().token(self.settings.telegram_bot_token).build()

        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("formats", self.formats_command))

        application.add_handler(
            MessageHandler(filters.Document.ALL | filters.PHOTO, self.handle_upload)
        )

        application.add_handler(
            MessageHandler(filters.ALL & ~(filters.COMMAND), self.unsupported_message)
        )
        return application

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Send me a supported file and I will convert it to PDF.\n"
            f"Max file size: {self.settings.max_file_mb} MB\n"
            f"Daily user limit: {self.settings.daily_conversions_per_user} conversions\n"
            "Use /formats to see supported file types."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "How it works:\n"
            "1) Upload one file.\n"
            "2) I validate and convert it to PDF.\n"
            "3) I return the PDF and immediately delete all temporary files.\n"
            f"4) You can convert up to {self.settings.daily_conversions_per_user} files per day."
        )

    async def formats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Supported formats: doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png, tiff, odt, rtf, txt"
        )

    async def unsupported_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Please send a file as a document or photo. Use /formats to check supported types."
        )

    async def handle_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        upload = self._extract_upload(message)

        if upload is None:
            await message.reply_text("Could not read this file. Please resend it as a document.")
            return

        job_id = uuid.uuid4().hex[:10]
        log_prefix = f"[job:{job_id}]"

        try:
            extension = validate_file(upload.filename, upload.file_size, self.settings.max_file_mb)
        except ConversionError as exc:
            await message.reply_text(self._user_message_for_error(exc))
            return

        requester_id = self._resolve_requester_id(update)
        allowed, remaining = await self._rate_limiter.try_consume(requester_id)
        if not allowed:
            await message.reply_text(
                f"Daily limit reached ({self.settings.daily_conversions_per_user} conversions). "
                "Please try again tomorrow."
            )
            return

        status_message = await message.reply_text("Processing your file. Please wait...")

        async with self._semaphore:
            job_dir = create_job_dir()
            input_path = job_dir / sanitize_filename(upload.filename)
            output_path: Path | None = None

            try:
                telegram_file = await context.bot.get_file(upload.file_id)
                await telegram_file.download_to_drive(custom_path=str(input_path))

                output_path = await self.provider.convert_to_pdf(
                    input_path=input_path,
                    extension=extension,
                    mime_type=upload.mime_type,
                )

                with output_path.open("rb") as fh:
                    await message.reply_document(
                        document=InputFile(fh, filename=f"{input_path.stem}.pdf"),
                        caption="Done. Converted to PDF.",
                    )
                await status_message.delete()
                LOGGER.info("%s conversion successful (remaining_today=%s)", log_prefix, remaining)
            except ConversionError as exc:
                LOGGER.warning("%s conversion error: %s", log_prefix, exc)
                await message.reply_text(self._user_message_for_error(exc))
            except Exception:
                LOGGER.exception("%s unhandled failure during conversion", log_prefix)
                await message.reply_text(
                    "Something went wrong while converting your file. Please try again shortly."
                )
            finally:
                cleanup_job_files(job_dir)

    @staticmethod
    def _resolve_requester_id(update: Update) -> int:
        if update.effective_user and update.effective_user.id:
            return int(update.effective_user.id)
        if update.effective_chat and update.effective_chat.id:
            return int(update.effective_chat.id)
        return 0

    @staticmethod
    def _extract_upload(message) -> IncomingUpload | None:
        if message.document:
            doc = message.document
            filename = sanitize_filename(doc.file_name or f"{doc.file_unique_id}.bin")
            return IncomingUpload(
                file_id=doc.file_id,
                filename=filename,
                file_size=doc.file_size or 0,
                mime_type=doc.mime_type,
            )

        if message.photo:
            photo = message.photo[-1]
            return IncomingUpload(
                file_id=photo.file_id,
                filename=f"photo_{photo.file_unique_id}.jpg",
                file_size=photo.file_size or 0,
                mime_type="image/jpeg",
            )

        return None

    @staticmethod
    def _user_message_for_error(exc: Exception) -> str:
        if isinstance(exc, UnsupportedFileError):
            return (
                "Unsupported file format. Use /formats for the current allowlist."
            )
        if isinstance(exc, FileTooLargeError):
            return str(exc)
        if isinstance(exc, ProviderTimeoutError):
            return "The conversion timed out. Please try again with a smaller file."
        if isinstance(exc, ProviderExecutionError):
            return "Conversion provider failed for this file. Please try another format."
        return "Conversion failed. Please try again."
