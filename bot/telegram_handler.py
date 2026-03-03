"""
bot/telegram_handler.py
=======================
Telegram Bot with multi-step ConversationHandler for UGC Video Pro.

Conversation flow:
    /start -> SELECT_MODE -> SELECT_MODEL -> SELECT_DURATION
            -> SELECT_LANGUAGE -> SEND_CONTENT -> CONFIRM_GENERATION -> GENERATING

Commands: /start, /cancel, /status, /help
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters,
)

from bot.messages import MESSAGES, get_message, get_model_name, get_mode_name, get_lang_name
from utils.logger import get_logger

logger = get_logger(__name__)

(
    SELECT_MODE, SELECT_MODEL, SELECT_DURATION, SELECT_LANGUAGE,
    SEND_CONTENT, AWAIT_IMAGE_AFTER_URL, CONFIRM_GENERATION, GENERATING,
) = range(8)


@dataclass
class VideoRequest:
    """Holds all parameters collected during the conversation."""
    user_id: int
    chat_id: int
    mode: str = ""
    model: str = ""
    duration: int = 30
    language: str = "zh"
    text_prompt: str = ""
    image_path: Optional[str] = None
    url: Optional[str] = None
    url_content: Optional[str] = None
    num_segments: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class GenerationProgress:
    """Tracks live progress of a video generation job."""
    request: VideoRequest
    status_message_id: Optional[int] = None
    current_segment: int = 0
    total_segments: int = 0
    started_at: float = field(default_factory=time.time)
    is_cancelled: bool = False


def build_mode_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_message("mode_image_to_video", lang), callback_data="mode:image_to_video")],
        [InlineKeyboardButton(get_message("mode_text_to_video", lang), callback_data="mode:text_to_video")],
        [InlineKeyboardButton(get_message("mode_url_to_video", lang), callback_data="mode:url_to_video")],
    ])


def build_model_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_message("model_veo_31_pro", lang), callback_data="model:veo_31_pro")],
        [InlineKeyboardButton(get_message("model_veo_3_pro", lang), callback_data="model:veo_3_pro")],
        [InlineKeyboardButton(get_message("model_veo_3", lang), callback_data="model:veo_3")],
        [InlineKeyboardButton(get_message("model_seedance_2", lang), callback_data="model:seedance_2")],
        [InlineKeyboardButton(get_message("model_sora_2_pro", lang), callback_data="model:sora_2_pro")],
        [InlineKeyboardButton(get_message("model_sora_2", lang), callback_data="model:sora_2")],
    ])


def build_duration_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_message("duration_15", lang), callback_data="dur:15"),
            InlineKeyboardButton(get_message("duration_25", lang), callback_data="dur:25"),
        ],
        [
            InlineKeyboardButton(get_message("duration_30", lang), callback_data="dur:30"),
            InlineKeyboardButton(get_message("duration_60", lang), callback_data="dur:60"),
        ],
        [InlineKeyboardButton(get_message("duration_120", lang), callback_data="dur:120")],
    ])


def build_language_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(get_message("lang_zh", lang), callback_data="lang:zh"),
        InlineKeyboardButton(get_message("lang_en", lang), callback_data="lang:en"),
        InlineKeyboardButton(get_message("lang_it", lang), callback_data="lang:it"),
    ]])


def build_confirm_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(get_message("btn_generate", lang), callback_data="confirm:yes"),
        InlineKeyboardButton(get_message("btn_cancel", lang), callback_data="confirm:no"),
    ]])


class UGCVideoBot:
    """Main Telegram Bot handler for UGC Video Pro."""

    def __init__(self, config: dict):
        self.config = config
        self.bot_token = config["telegram"]["bot_token"]
        self.allowed_users = set(config["telegram"].get("allowed_users", []))
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._active_jobs: dict[int, GenerationProgress] = {}
        self._orchestrator = None

    def _get_orchestrator(self):
        if self._orchestrator is None:
            from core.orchestrator import VideoOrchestrator
            self._orchestrator = VideoOrchestrator(self.config)
        return self._orchestrator

    def _is_allowed(self, user_id: int) -> bool:
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users

    def _get_user_lang(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        return context.user_data.get("language", "zh")

    async def _download_image(self, bot: Bot, file_id: str, suffix: str = ".jpg") -> str:
        file = await bot.get_file(file_id)
        dest = self.output_dir / f"input_{int(time.time())}_{file_id[:8]}{suffix}"
        await file.download_to_drive(str(dest))
        return str(dest)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = update.effective_user
        lang = "zh"
        if not self._is_allowed(user.id):
            await update.message.reply_text(get_message("error_no_permission", lang))
            return ConversationHandler.END
        context.user_data.clear()
        context.user_data["language"] = lang
        logger.info(f"User {user.id} ({user.username}) started conversation")
        await update.message.reply_text(
            get_message("welcome", lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_mode_keyboard(lang),
        )
        return SELECT_MODE

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lang = self._get_user_lang(context)
        await update.message.reply_text(get_message("help", lang), parse_mode=ParseMode.MARKDOWN)

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        lang = self._get_user_lang(context)
        user_id = update.effective_user.id
        if user_id in self._active_jobs:
            self._active_jobs[user_id].is_cancelled = True
            del self._active_jobs[user_id]
        context.user_data.clear()
        await update.message.reply_text(get_message("cancel", lang))
        return ConversationHandler.END

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lang = self._get_user_lang(context)
        user_id = update.effective_user.id
        job = self._active_jobs.get(user_id)
        if not job:
            await update.message.reply_text("No active generation job." if lang == "en" else "暂无进行中的生成任务。")
            return
        elapsed = int(time.time() - job.started_at)
        text = get_message(
            "generating", lang,
            segment=job.current_segment, total=job.total_segments,
            model=get_model_name(job.request.model), duration=job.request.duration,
            segment_prompt="...", eta=f"{max(0, job.total_segments * 60 - elapsed)}s",
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def step_select_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        lang = self._get_user_lang(context)
        mode = query.data.split(":")[1]
        context.user_data["mode"] = mode
        logger.debug(f"User {query.from_user.id} selected mode: {mode}")
        await query.edit_message_text(
            get_message("select_model", lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_model_keyboard(lang),
        )
        return SELECT_MODEL

    async def step_select_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        lang = self._get_user_lang(context)
        model = query.data.split(":")[1]
        context.user_data["model"] = model
        logger.debug(f"User {query.from_user.id} selected model: {model}")
        await query.edit_message_text(
            get_message("select_duration", lang),
            reply_markup=build_duration_keyboard(lang),
        )
        return SELECT_DURATION

    async def step_select_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        lang = self._get_user_lang(context)
        duration = int(query.data.split(":")[1])
        context.user_data["duration"] = duration
        await query.edit_message_text(
            get_message("select_language", lang),
            reply_markup=build_language_keyboard(lang),
        )
        return SELECT_LANGUAGE

    async def step_select_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        selected_lang = query.data.split(":")[1]
        context.user_data["language"] = selected_lang
        lang = selected_lang
        mode = context.user_data.get("mode", "image_to_video")
        if mode == "text_to_video":
            await query.edit_message_text(get_message("send_text", lang), parse_mode=ParseMode.MARKDOWN)
        elif mode == "image_to_video":
            await query.edit_message_text(get_message("send_image", lang), parse_mode=ParseMode.MARKDOWN)
        elif mode == "url_to_video":
            await query.edit_message_text(get_message("send_url_and_image", lang), parse_mode=ParseMode.MARKDOWN)
        return SEND_CONTENT

    async def step_receive_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        lang = self._get_user_lang(context)
        mode = context.user_data.get("mode")
        if mode == "url_to_video":
            text = update.message.text.strip()
            if not text.startswith("http"):
                await update.message.reply_text(get_message("error_invalid_url", lang), parse_mode=ParseMode.MARKDOWN)
                return SEND_CONTENT
            context.user_data["url"] = text
            await update.message.reply_text(get_message("send_image_after_url", lang), parse_mode=ParseMode.MARKDOWN)
            return AWAIT_IMAGE_AFTER_URL
        elif mode == "text_to_video":
            context.user_data["text_prompt"] = update.message.text.strip()
            return await self._show_confirm(update, context)
        else:
            await update.message.reply_text(get_message("send_image", lang), parse_mode=ParseMode.MARKDOWN)
            return SEND_CONTENT

    async def step_receive_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        lang = self._get_user_lang(context)
        photo = update.message.photo[-1]
        try:
            image_path = await self._download_image(update.get_bot(), photo.file_id, suffix=".jpg")
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            await update.message.reply_text(get_message("error", lang, error=str(e)), parse_mode=ParseMode.MARKDOWN)
            return SEND_CONTENT
        context.user_data["image_path"] = image_path
        logger.info(f"Downloaded product image: {image_path}")
        return await self._show_confirm(update, context)

    async def step_receive_photo_after_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        lang = self._get_user_lang(context)
        photo = update.message.photo[-1]
        try:
            image_path = await self._download_image(update.get_bot(), photo.file_id, suffix=".jpg")
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            await update.message.reply_text(get_message("error", lang, error=str(e)), parse_mode=ParseMode.MARKDOWN)
            return AWAIT_IMAGE_AFTER_URL
        context.user_data["image_path"] = image_path
        return await self._show_confirm(update, context)

    async def _show_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        lang = self._get_user_lang(context)
        data = context.user_data
        from models.base import get_model_max_duration
        model = data.get("model", "veo_3")
        duration = data.get("duration", 30)
        max_clip = get_model_max_duration(model)
        num_segments = -(-duration // max_clip)
        context.user_data["num_segments"] = num_segments
        text = get_message(
            "generation_summary", lang,
            mode=get_mode_name(data.get("mode", ""), lang),
            model=get_model_name(model),
            duration=duration, segments=num_segments,
            language=get_lang_name(lang, lang),
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_confirm_keyboard(lang))
        return CONFIRM_GENERATION

    async def step_confirm_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        lang = self._get_user_lang(context)
        choice = query.data.split(":")[1]
        if choice == "no":
            await query.edit_message_text(get_message("cancel", lang))
            context.user_data.clear()
            return ConversationHandler.END
        data = context.user_data
        request = VideoRequest(
            user_id=query.from_user.id, chat_id=query.message.chat_id,
            mode=data.get("mode", "image_to_video"), model=data.get("model", "veo_3"),
            duration=data.get("duration", 30), language=lang,
            text_prompt=data.get("text_prompt", ""),
            image_path=data.get("image_path"), url=data.get("url"),
            num_segments=data.get("num_segments", 1),
        )
        status_msg = await query.edit_message_text(
            get_message("analyzing_image", lang) if request.image_path
            else get_message("generating_script", lang, segments=request.num_segments),
            parse_mode=ParseMode.MARKDOWN,
        )
        progress = GenerationProgress(
            request=request, status_message_id=status_msg.message_id,
            total_segments=request.num_segments,
        )
        self._active_jobs[request.user_id] = progress
        asyncio.create_task(self._run_generation(query.message.chat_id, request, progress, context))
        return GENERATING

    async def _run_generation(
        self, chat_id: int, request: VideoRequest,
        progress: GenerationProgress, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        lang = request.language
        bot = context.bot
        start_time = time.time()
        try:
            orchestrator = self._get_orchestrator()

            async def update_progress(segment: int, total: int, model: str, prompt: str, eta: str):
                if progress.is_cancelled:
                    raise asyncio.CancelledError("Generation cancelled by user")
                progress.current_segment = segment
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=progress.status_message_id,
                        text=get_message(
                            "generating", lang, segment=segment, total=total,
                            model=model, duration=request.duration,
                            segment_prompt=prompt[:60] + "..." if len(prompt) > 60 else prompt, eta=eta,
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

            async def update_status(msg_key: str, **kwargs):
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=progress.status_message_id,
                        text=get_message(msg_key, lang, **kwargs), parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

            result = await orchestrator.generate(
                request, progress_callback=update_progress, status_callback=update_status,
            )

            if progress.is_cancelled:
                return

            elapsed_secs = int(time.time() - start_time)
            elapsed_str = f"{elapsed_secs // 60}m {elapsed_secs % 60}s"

            final_text = get_message(
                "complete", lang, model=get_model_name(request.model),
                duration=request.duration, segments=request.num_segments,
                elapsed=elapsed_str, filename=Path(result.video_path).name,
            )

            await bot.edit_message_text(
                chat_id=chat_id, message_id=progress.status_message_id,
                text=final_text, parse_mode=ParseMode.MARKDOWN,
            )

            video_path = Path(result.video_path)
            if video_path.exists():
                file_size = video_path.stat().st_size
                max_size = self.config.get("video", {}).get("telegram_max_size", 52_428_800)
                if file_size <= max_size:
                    with open(video_path, "rb") as video_file:
                        await bot.send_video(
                            chat_id=chat_id, video=video_file,
                            caption=f"UGC Video | {get_model_name(request.model)} | {request.duration}s",
                            supports_streaming=True, width=720, height=1280,
                        )
                else:
                    with open(video_path, "rb") as video_file:
                        await bot.send_document(
                            chat_id=chat_id, document=video_file,
                            caption=f"UGC Video (large file) | {get_model_name(request.model)} | {request.duration}s",
                        )

            if result.drive_link:
                await bot.send_message(
                    chat_id=chat_id,
                    text=get_message("drive_complete", lang, link=result.drive_link),
                    parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False,
                )

        except asyncio.CancelledError:
            await bot.send_message(chat_id=chat_id, text=get_message("cancel", lang))
        except Exception as e:
            logger.exception(f"Generation failed for user {request.user_id}: {e}")
            error_text = get_message("error", lang, error=str(e)[:200])
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=progress.status_message_id,
                    text=error_text, parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                await bot.send_message(chat_id=chat_id, text=error_text, parse_mode=ParseMode.MARKDOWN)
        finally:
            self._active_jobs.pop(request.user_id, None)
            if request.image_path and Path(request.image_path).exists():
                try:
                    os.unlink(request.image_path)
                except Exception:
                    pass

    async def fallback_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lang = self._get_user_lang(context)
        await update.message.reply_text(get_message("unknown_command", lang))

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Update error: {context.error}", exc_info=context.error)

    def build_application(self) -> Application:
        app = (
            Application.builder().token(self.bot_token)
            .read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()
        )

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.cmd_start)],
            states={
                SELECT_MODE: [CallbackQueryHandler(self.step_select_mode, pattern=r"^mode:")],
                SELECT_MODEL: [CallbackQueryHandler(self.step_select_model, pattern=r"^model:")],
                SELECT_DURATION: [CallbackQueryHandler(self.step_select_duration, pattern=r"^dur:")],
                SELECT_LANGUAGE: [CallbackQueryHandler(self.step_select_language, pattern=r"^lang:")],
                SEND_CONTENT: [
                    MessageHandler(filters.PHOTO, self.step_receive_photo),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.step_receive_text),
                ],
                AWAIT_IMAGE_AFTER_URL: [
                    MessageHandler(filters.PHOTO, self.step_receive_photo_after_url),
                ],
                CONFIRM_GENERATION: [
                    CallbackQueryHandler(self.step_confirm_generation, pattern=r"^confirm:"),
                ],
                GENERATING: [
                    CommandHandler("cancel", self.cmd_cancel),
                    MessageHandler(filters.ALL, self.fallback_unknown),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cmd_cancel),
                CommandHandler("start", self.cmd_start),
            ],
            allow_reentry=True,
            conversation_timeout=3600,
        )

        app.add_handler(conv_handler)
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_error_handler(self.error_handler)
        return app

    async def run(self) -> None:
        app = self.build_application()
        logger.info("Bot starting — polling for updates...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("Bot shutting down...")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
