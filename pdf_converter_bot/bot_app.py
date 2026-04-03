from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
from .validation import normalize_extension, sanitize_filename, validate_file

LOGGER = logging.getLogger(__name__)

SPLIT_RANGES_PATTERN = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")


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

        self._pending_files: dict[int, IncomingUpload] = {}
        self._merge_waiting: dict[int, IncomingUpload] = {}
        self._split_waiting: dict[int, IncomingUpload] = {}

    def build_application(self, enable_updater: bool = True) -> Application:
        builder = Application.builder().token(self.settings.telegram_bot_token)
        if not enable_updater:
            builder = builder.updater(None)
        application = builder.build()

        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("formats", self.formats_command))

        application.add_handler(CallbackQueryHandler(self.handle_action_callback, pattern=r"^act:"))
        application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, self.handle_upload))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))

        application.add_handler(MessageHandler(filters.ALL & ~(filters.COMMAND), self.unsupported_message))
        return application

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Send a file and I will show what I can do with it.\n"
            "For PDF files: merge, split, compress.\n"
            "For non-PDF files: convert to PDF."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "How it works:\n"
            "1) Send one file.\n"
            "2) Choose an action from buttons.\n"
            "3) I process and return result, then delete temp files.\n"
            f"Daily user limit: {self.settings.daily_conversions_per_user} operations."
        )

    async def formats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Supported conversion formats: doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png, tiff, odt, rtf, txt"
        )

    async def unsupported_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await update.effective_message.reply_text(
            "Please send a file as a document or photo."
        )

    async def handle_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        upload = self._extract_upload(message)
        if upload is None:
            await message.reply_text("Could not read this file. Please resend it as a document.")
            return

        user_id = self._resolve_requester_id(update)

        if user_id in self._merge_waiting:
            await self._handle_merge_second_file(user_id, upload, message, context)
            return

        self._pending_files[user_id] = upload
        await self._send_action_options(message, upload)

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user_id = self._resolve_requester_id(update)

        if user_id not in self._split_waiting:
            await self.unsupported_message(update, context)
            return

        ranges_text = (message.text or "").replace(" ", "")
        if not self._is_valid_split_ranges(ranges_text):
            await message.reply_text(
                "Invalid range format. Example: 1-3,5,8-10"
            )
            return

        if not await self._consume_daily_limit(user_id, message):
            self._split_waiting.pop(user_id, None)
            return

        upload = self._split_waiting.pop(user_id)
        await self._run_pdf_tool_operation(
            message=message,
            context=context,
            uploads=[upload],
            tool="split",
            process_params={"split_mode": "ranges", "ranges": ranges_text},
            output_basename=Path(upload.filename).stem,
            progress_text="Splitting PDF...",
            success_caption="Done. Split operation finished.",
        )

    async def handle_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return

        await query.answer()
        user_id = self._resolve_requester_id(update)
        action = (query.data or "").replace("act:", "", 1)
        message = query.message
        if message is None:
            return

        upload = self._pending_files.get(user_id)
        if upload is None:
            await query.edit_message_text("Send a file first, then choose an action.")
            return

        extension = normalize_extension(upload.filename)

        if action == "convert":
            if extension == "pdf":
                await query.edit_message_text("This file is already a PDF. Choose merge/split/compress.")
                return

            if not await self._consume_daily_limit(user_id, message):
                self._pending_files.pop(user_id, None)
                return

            self._pending_files.pop(user_id, None)
            await query.edit_message_text("Converting to PDF...")
            await self._run_convert_operation(message, context, upload)
            return

        if extension != "pdf":
            await query.edit_message_text("This action requires a PDF file. Send a PDF and try again.")
            return

        if action == "compress":
            if not await self._consume_daily_limit(user_id, message):
                self._pending_files.pop(user_id, None)
                return

            self._pending_files.pop(user_id, None)
            await query.edit_message_text("Compressing PDF...")
            await self._run_pdf_tool_operation(
                message=message,
                context=context,
                uploads=[upload],
                tool="compress",
                process_params={"compression_level": "recommended"},
                output_basename=Path(upload.filename).stem,
                progress_text="Compressing PDF...",
                success_caption="Done. Compression finished.",
            )
            return

        if action == "split":
            self._pending_files.pop(user_id, None)
            self._split_waiting[user_id] = upload
            await query.edit_message_text(
                "Send page ranges to split. Example: 1-3,5,8-10"
            )
            return

        if action == "merge":
            self._pending_files.pop(user_id, None)
            self._merge_waiting[user_id] = upload
            await query.edit_message_text(
                "Send one more PDF file to merge with this one."
            )
            return

        await query.edit_message_text("Unknown action. Send file again.")

    async def _send_action_options(self, message, upload: IncomingUpload) -> None:
        extension = normalize_extension(upload.filename)

        if extension == "pdf":
            keyboard = [
                [InlineKeyboardButton("Merge PDF", callback_data="act:merge")],
                [InlineKeyboardButton("Split PDF", callback_data="act:split")],
                [InlineKeyboardButton("Compress PDF", callback_data="act:compress")],
            ]
            text = "I received your PDF. Choose what you want to do."
        else:
            keyboard = [
                [InlineKeyboardButton("Convert to PDF", callback_data="act:convert")],
            ]
            text = "I received your file. Choose an action."

        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _handle_merge_second_file(
        self,
        user_id: int,
        second_upload: IncomingUpload,
        message,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        first_upload = self._merge_waiting.get(user_id)
        if first_upload is None:
            await message.reply_text("Merge session expired. Please start again.")
            return

        if normalize_extension(second_upload.filename) != "pdf":
            await message.reply_text("Please send a PDF file to complete merge.")
            return

        self._merge_waiting.pop(user_id, None)

        if not await self._consume_daily_limit(user_id, message):
            return

        await self._run_pdf_tool_operation(
            message=message,
            context=context,
            uploads=[first_upload, second_upload],
            tool="merge",
            process_params=None,
            output_basename="merged",
            progress_text="Merging PDF files...",
            success_caption="Done. Merge finished.",
        )

    async def _consume_daily_limit(self, user_id: int, message) -> bool:
        allowed, _remaining = await self._rate_limiter.try_consume(user_id)
        if allowed:
            return True

        await message.reply_text(
            f"Daily limit reached ({self.settings.daily_conversions_per_user} operations). "
            "Please try again tomorrow."
        )
        return False

    async def _run_convert_operation(
        self,
        message,
        context: ContextTypes.DEFAULT_TYPE,
        upload: IncomingUpload,
    ) -> None:
        try:
            extension = validate_file(upload.filename, upload.file_size, self.settings.max_file_mb)
        except ConversionError as exc:
            await message.reply_text(self._user_message_for_error(exc))
            return

        await self._run_job(
            message=message,
            context=context,
            uploads=[upload],
            progress_text="Converting to PDF...",
            operation=lambda paths: self.provider.convert_to_pdf(paths[0][0], extension, paths[0][1]),
            success_caption="Done. Converted to PDF.",
        )

    async def _run_pdf_tool_operation(
        self,
        message,
        context: ContextTypes.DEFAULT_TYPE,
        uploads: list[IncomingUpload],
        tool: str,
        process_params: dict[str, Any] | None,
        output_basename: str,
        progress_text: str,
        success_caption: str,
    ) -> None:
        try:
            for upload in uploads:
                ext = normalize_extension(upload.filename)
                if ext != "pdf":
                    raise UnsupportedFileError("This action requires PDF files only.")
                validate_file(upload.filename, upload.file_size, self.settings.max_file_mb)
        except ConversionError as exc:
            await message.reply_text(self._user_message_for_error(exc))
            return

        await self._run_job(
            message=message,
            context=context,
            uploads=uploads,
            progress_text=progress_text,
            operation=lambda paths: self.provider.process_files(
                tool=tool,
                inputs=paths,
                output_basename=output_basename,
                process_params=process_params,
            ),
            success_caption=success_caption,
        )

    async def _run_job(
        self,
        message,
        context: ContextTypes.DEFAULT_TYPE,
        uploads: list[IncomingUpload],
        progress_text: str,
        operation,
        success_caption: str,
    ) -> None:
        job_id = uuid.uuid4().hex[:10]
        log_prefix = f"[job:{job_id}]"
        status_message = await message.reply_text(progress_text)

        async with self._semaphore:
            job_dir = create_job_dir()

            try:
                downloaded_inputs: list[tuple[Path, str | None]] = []
                for upload in uploads:
                    input_path = job_dir / sanitize_filename(upload.filename)
                    telegram_file = await context.bot.get_file(upload.file_id)
                    await telegram_file.download_to_drive(custom_path=str(input_path))
                    downloaded_inputs.append((input_path, upload.mime_type))

                output_path: Path = await operation(downloaded_inputs)

                with output_path.open("rb") as fh:
                    await message.reply_document(
                        document=InputFile(fh, filename=output_path.name),
                        caption=success_caption,
                    )

                try:
                    await status_message.delete()
                except Exception:
                    pass

                LOGGER.info("%s operation successful", log_prefix)
            except ConversionError as exc:
                LOGGER.warning("%s conversion error: %s", log_prefix, exc)
                await message.reply_text(self._user_message_for_error(exc))
            except Exception:
                LOGGER.exception("%s unhandled failure during operation", log_prefix)
                await message.reply_text(
                    "Something went wrong while processing your file. Please try again shortly."
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
    def _is_valid_split_ranges(ranges: str) -> bool:
        if not ranges or not SPLIT_RANGES_PATTERN.match(ranges):
            return False

        for part in ranges.split(","):
            if "-" not in part:
                continue
            start_str, end_str = part.split("-", 1)
            if int(start_str) > int(end_str):
                return False

        return True

    @staticmethod
    def _user_message_for_error(exc: Exception) -> str:
        if isinstance(exc, UnsupportedFileError):
            return "Unsupported file/action combination."
        if isinstance(exc, FileTooLargeError):
            return str(exc)
        if isinstance(exc, ProviderTimeoutError):
            return "The operation timed out. Please try again with a smaller file."
        if isinstance(exc, ProviderExecutionError):
            return "Processing provider failed for this request. Please try again."
        return "Operation failed. Please try again."


