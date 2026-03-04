"""
bot/telegram_handler.py
=======================
Telegram Bot with multi-step ConversationHandler for UGC Video Pro.

Conversation flow:
    /start
      → SELECT_MODE (text_to_video | image_to_video | url_to_video)
      → SELECT_MODEL (sora_2 | sora_2_pro | seedance_2 | veo_3 | veo_3_pro | veo_31_pro)
      → SELECT_DURATION (dynamic multiples of model clip duration | custom input)
      → SELECT_LANGUAGE (zh | en | it)
      → SEND_CONTENT (text / photo / url+photo depending on mode)
      → ASK_DESCRIPTION (if photo uploaded: ask whether to add product description)
      → (generation pipeline runs)
      → Video sent to user

Commands:
    /start   - Begin or restart conversation
    /cancel  - Cancel current operation
    /status  - Show current generation status
    /help    - Show help message
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.messages import (
    MESSAGES,
    get_message,
    get_model_name,
    get_mode_name,
    get_lang_name,
)
from models.base import (
    get_model_max_duration,
    get_valid_duration_multiples,
    nearest_valid_duration,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
# Conversation states
# ─────────────────────────────────────────────────────────────
(
    SELECT_MODE,
    SELECT_MODEL,
    SELECT_DURATION,
    SELECT_LANGUAGE,
    SEND_CONTENT,
    AWAIT_IMAGE_AFTER_URL,
    CONFIRM_GENERATION,
    GENERATING,
    CUSTOM_DURATION,
    ASK_DESCRIPTION,
    INPUT_DESCRIPTION,
) = range(11)

# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class VideoRequest:
    """Holds all parameters collected during the conversation."""
    user_id: int
    chat_id: int
    mode: str = ""                  # text_to_video | image_to_video | url_to_video
    model: str = ""                 # sora_2 | sora_2_pro | seedance_2 | veo_3 | ...
    duration: int = 30              # seconds
    language: str = "zh"           # zh | en | it
    text_prompt: str = ""          # for text_to_video
    image_path: Optional[str] = None    # local path to downloaded product image
    url: Optional[str] = None          # for url_to_video mode
    url_content: Optional[str] = None  # extracted text from URL
    num_segments: int = 0          # calculated from duration/model
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


# ─────────────────────────────────────────────────────────────
# Inline keyboard builders
# ─────────────────────────────────────────────────────────────

def build_mode_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            get_message("mode_image_to_video", lang),
            callback_data="mode:image_to_video"
        )],
        [InlineKeyboardButton(
            get_message("mode_text_to_video", lang),
            callback_data="mode:text_to_video"
        )],
        [InlineKeyboardButton(
            get_message("mode_url_to_video", lang),
            callback_data="mode:url_to_video"
        )],
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


def build_duration_keyboard(model: str, lang: str = "zh") -> InlineKeyboardMarkup:
    """Build dynamic duration keyboard based on model's max clip duration.
    
    Shows multiples of the model's max_duration (e.g. 8, 16, 24, 32, 40 for Veo 8s)
    plus a custom input option.
    """
    multiples = get_valid_duration_multiples(model, max_total=120, count=5)
    rows = []
    # Build rows of 2 buttons each
    for i in range(0, len(multiples), 2):
        row = []
        for dur in multiples[i:i+2]:
            label = get_message("duration_n_sec", lang, n=dur)
            row.append(InlineKeyboardButton(label, callback_data=f"dur:{dur}"))
        rows.append(row)
    # Add custom input button
    rows.append([
        InlineKeyboardButton(
            get_message("duration_custom", lang),
            callback_data="dur:custom"
        )
    ])
    return InlineKeyboardMarkup(rows)


def build_language_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_message("lang_zh", lang), callback_data="lang:zh"),
            InlineKeyboardButton(get_message("lang_en", lang), callback_data="lang:en"),
            InlineKeyboardButton(get_message("lang_it", lang), callback_data="lang:it"),
        ],
    ])


def build_confirm_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_message("btn_generate", lang), callback_data="confirm:yes"),
            InlineKeyboardButton(get_message("btn_cancel", lang), callback_data="confirm:no"),
        ],
    ])


# ─────────────────────────────────────────────────────────────
# Main Bot class
# ─────────────────────────────────────────────────────────────

class UGCVideoBot:
    """Main Telegram Bot handler for UGC Video Pro."""

    def __init__(self, config: dict):
        self.config = config
        self.bot_token = config["telegram"]["bot_token"]
        self.allowed_users = set(config["telegram"].get("allowed_users", []))
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Active generation jobs: user_id -> GenerationProgress
        self._active_jobs: dict[int, GenerationProgress] = {}

        # Initialize the orchestrator lazily (heavy imports)
        self._orchestrator = None

    def _get_orchestrator(self):
        """Lazy-initialize the video orchestrator."""
        if self._orchestrator is None:
            from core.orchestrator import VideoOrchestrator
            self._orchestrator = VideoOrchestrator(self.config)
        return self._orchestrator

    def _is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.allowed_users:
            return True  # All users allowed
        return user_id in self.allowed_users

    def _get_user_lang(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Get user's selected language from context, defaulting to zh."""
        return context.user_data.get("language", "zh")

    async def _download_image(self, bot: Bot, file_id: str, suffix: str = ".jpg") -> str:
        """Download a Telegram file to local disk. Returns local path."""
        file = await bot.get_file(file_id)
        dest = self.output_dir / f"input_{int(time.time())}_{file_id[:8]}{suffix}"
        await file.download_to_drive(str(dest))
        return str(dest)

    # ─────────────────────────────────────────────────────────
    # Command handlers
    # ─────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /start command — entry point of the conversation."""
        user = update.effective_user
        lang = "zh"  # Default to Chinese on start

        if not self._is_allowed(user.id):
            await update.message.reply_text(get_message("error_no_permission", lang))
            return ConversationHandler.END

        # Reset user state
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
        """Handle /help command."""
        lang = self._get_user_lang(context)
        await update.message.reply_text(
            get_message("help", lang),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /cancel command."""
        lang = self._get_user_lang(context)
        user_id = update.effective_user.id

        # Cancel any active job
        if user_id in self._active_jobs:
            self._active_jobs[user_id].is_cancelled = True
            del self._active_jobs[user_id]

        context.user_data.clear()
        await update.message.reply_text(get_message("cancel", lang))
        return ConversationHandler.END

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show current generation status."""
        lang = self._get_user_lang(context)
        user_id = update.effective_user.id
        job = self._active_jobs.get(user_id)

        if not job:
            await update.message.reply_text("No active generation job." if lang == "en" else "暂无进行中的生成任务。")
            return

        elapsed = int(time.time() - job.started_at)
        text = get_message(
            "generating", lang,
            segment=job.current_segment,
            total=job.total_segments,
            model=get_model_name(job.request.model),
            duration=job.request.duration,
            segment_prompt="...",
            eta=f"{max(0, job.total_segments * 60 - elapsed)}s",
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    # ─────────────────────────────────────────────────────────
    # Conversation step handlers
    # ─────────────────────────────────────────────────────────

    async def step_select_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle mode selection callback."""
        query = update.callback_query
        await query.answer()

        lang = self._get_user_lang(context)
        mode = query.data.split(":")[1]  # "mode:image_to_video" -> "image_to_video"
        context.user_data["mode"] = mode

        logger.debug(f"User {query.from_user.id} selected mode: {mode}")

        await query.edit_message_text(
            get_message("select_model", lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_model_keyboard(lang),
        )
        return SELECT_MODEL

    async def step_select_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle model selection callback."""
        query = update.callback_query
        await query.answer()

        lang = self._get_user_lang(context)
        model = query.data.split(":")[1]  # "model:veo_31_pro" -> "veo_31_pro"
        context.user_data["model"] = model

        logger.debug(f"User {query.from_user.id} selected model: {model}")

        max_clip = get_model_max_duration(model)
        await query.edit_message_text(
            get_message("select_duration", lang, max_clip=max_clip),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_duration_keyboard(model, lang),
        )
        return SELECT_DURATION

    async def step_select_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle duration selection callback."""
        query = update.callback_query
        await query.answer()

        lang = self._get_user_lang(context)
        raw = query.data.split(":")[1]  # "dur:30" -> "30" or "dur:custom" -> "custom"

        if raw == "custom":
            # Transition to custom duration text input
            model = context.user_data.get("model", "veo_3")
            max_clip = get_model_max_duration(model)
            examples = ", ".join(str(v) for v in get_valid_duration_multiples(model, 120, 5))
            await query.edit_message_text(
                get_message("duration_custom_prompt", lang, max_clip=max_clip, examples=examples),
                parse_mode=ParseMode.MARKDOWN,
            )
            return CUSTOM_DURATION

        duration = int(raw)
        context.user_data["duration"] = duration

        logger.debug(f"User {query.from_user.id} selected duration: {duration}s")

        await query.edit_message_text(
            get_message("select_language", lang),
            reply_markup=build_language_keyboard(lang),
        )
        return SELECT_LANGUAGE

    async def step_custom_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle custom duration text input with validation."""
        lang = self._get_user_lang(context)
        model = context.user_data.get("model", "veo_3")
        max_clip = get_model_max_duration(model)
        text = update.message.text.strip()

        # Parse the number
        try:
            value = int(text)
        except ValueError:
            examples = ", ".join(str(v) for v in get_valid_duration_multiples(model, 120, 5))
            await update.message.reply_text(
                get_message("duration_custom_prompt", lang, max_clip=max_clip, examples=examples),
                parse_mode=ParseMode.MARKDOWN,
            )
            return CUSTOM_DURATION

        # Check if it's a valid multiple
        if value > 0 and value % max_clip == 0:
            context.user_data["duration"] = value
            logger.debug(f"User {update.effective_user.id} custom duration: {value}s")
            await update.message.reply_text(
                get_message("select_language", lang),
                reply_markup=build_language_keyboard(lang),
            )
            return SELECT_LANGUAGE

        # Not a valid multiple — show hint with nearest value
        nearest = nearest_valid_duration(model, value)
        hint_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                get_message("duration_use_nearest", lang, nearest=nearest),
                callback_data=f"dur:{nearest}",
            )],
        ])
        await update.message.reply_text(
            get_message("duration_invalid_hint", lang,
                        value=value, max_clip=max_clip, nearest=nearest),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=hint_keyboard,
        )
        return SELECT_DURATION

    async def step_select_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle language selection callback. Transitions to content input."""
        query = update.callback_query
        await query.answer()

        selected_lang = query.data.split(":")[1]  # "lang:zh" -> "zh"
        context.user_data["language"] = selected_lang
        lang = selected_lang  # Use newly selected language from here on

        mode = context.user_data.get("mode", "image_to_video")
        logger.debug(f"User {query.from_user.id} selected language: {selected_lang}, mode: {mode}")

        # Show appropriate content prompt based on mode
        if mode == "text_to_video":
            await query.edit_message_text(
                get_message("send_text", lang),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif mode == "image_to_video":
            await query.edit_message_text(
                get_message("send_image", lang),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif mode == "url_to_video":
            await query.edit_message_text(
                get_message("send_url_and_image", lang),
                parse_mode=ParseMode.MARKDOWN,
            )

        return SEND_CONTENT

    async def step_receive_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle text message for text_to_video mode."""
        lang = self._get_user_lang(context)
        mode = context.user_data.get("mode")

        if mode == "url_to_video":
            # First message in URL mode = the URL itself
            text = update.message.text.strip()
            if not text.startswith("http"):
                await update.message.reply_text(
                    get_message("error_invalid_url", lang),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return SEND_CONTENT

            context.user_data["url"] = text
            await update.message.reply_text(
                get_message("send_image_after_url", lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            return AWAIT_IMAGE_AFTER_URL

        elif mode == "text_to_video":
            context.user_data["text_prompt"] = update.message.text.strip()
            return await self._show_confirm(update, context)

        else:
            # image_to_video mode: user sent text instead of image
            await update.message.reply_text(
                get_message("send_image", lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            return SEND_CONTENT

    async def step_receive_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle photo upload for image_to_video mode."""
        lang = self._get_user_lang(context)

        # Get highest-resolution photo
        photo = update.message.photo[-1]

        # Check file size (approx, Telegram doesn't give exact size here)
        # Telegram max photo size via bot is ~20MB
        try:
            image_path = await self._download_image(
                update.get_bot(), photo.file_id, suffix=".jpg"
            )
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            await update.message.reply_text(
                get_message("error", lang, error=str(e)),
                parse_mode=ParseMode.MARKDOWN,
            )
            return SEND_CONTENT

        context.user_data["image_path"] = image_path
        logger.info(f"Downloaded product image: {image_path}")

        return await self._ask_description(update, context)

    async def step_receive_photo_after_url(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle photo upload after URL has been provided (URL mode)."""
        lang = self._get_user_lang(context)

        photo = update.message.photo[-1]
        try:
            image_path = await self._download_image(
                update.get_bot(), photo.file_id, suffix=".jpg"
            )
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            await update.message.reply_text(
                get_message("error", lang, error=str(e)),
                parse_mode=ParseMode.MARKDOWN,
            )
            return AWAIT_IMAGE_AFTER_URL

        context.user_data["image_path"] = image_path
        return await self._ask_description(update, context)

    async def _ask_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Ask user whether to add a product description after image upload."""
        lang = self._get_user_lang(context)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    get_message("btn_yes_add_desc", lang),
                    callback_data="desc:yes",
                ),
                InlineKeyboardButton(
                    get_message("btn_no_skip_desc", lang),
                    callback_data="desc:no",
                ),
            ]
        ])
        await update.message.reply_text(
            get_message("ask_add_description", lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return ASK_DESCRIPTION

    async def step_ask_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle the yes/no callback for product description."""
        query = update.callback_query
        await query.answer()

        lang = self._get_user_lang(context)
        choice = query.data.split(":")[1]  # "desc:yes" or "desc:no"

        if choice == "yes":
            await query.edit_message_text(
                get_message("send_product_description", lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            return INPUT_DESCRIPTION

        # User chose to skip — go directly to confirm
        return await self._show_confirm_from_callback(query, context)

    async def step_input_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle user-provided product description text."""
        context.user_data["text_prompt"] = update.message.text.strip()
        logger.info(f"User {update.effective_user.id} added product description")
        return await self._show_confirm(update, context)

    async def _show_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Show generation confirmation summary with inline keyboard."""
        lang = self._get_user_lang(context)
        data = context.user_data

        # Calculate number of segments
        model = data.get("model", "veo_3")
        duration = data.get("duration", 30)
        max_clip = get_model_max_duration(model)
        num_segments = -(-duration // max_clip)  # Ceil division

        context.user_data["num_segments"] = num_segments

        text = get_message(
            "generation_summary", lang,
            mode=get_mode_name(data.get("mode", ""), lang),
            model=get_model_name(model),
            duration=duration,
            segments=num_segments,
            language=get_lang_name(lang, lang),
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_confirm_keyboard(lang),
        )
        return CONFIRM_GENERATION

    async def _show_confirm_from_callback(
        self, query, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Show generation confirmation from a callback query (e.g. skip description)."""
        lang = self._get_user_lang(context)
        data = context.user_data

        model = data.get("model", "veo_3")
        duration = data.get("duration", 30)
        max_clip = get_model_max_duration(model)
        num_segments = -(-duration // max_clip)

        context.user_data["num_segments"] = num_segments

        text = get_message(
            "generation_summary", lang,
            mode=get_mode_name(data.get("mode", ""), lang),
            model=get_model_name(model),
            duration=duration,
            segments=num_segments,
            language=get_lang_name(lang, lang),
        )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_confirm_keyboard(lang),
        )
        return CONFIRM_GENERATION

    async def step_confirm_generation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle confirmation callback — launch generation or cancel."""
        query = update.callback_query
        await query.answer()

        lang = self._get_user_lang(context)
        choice = query.data.split(":")[1]  # "confirm:yes" or "confirm:no"

        if choice == "no":
            await query.edit_message_text(get_message("cancel", lang))
            context.user_data.clear()
            return ConversationHandler.END

        # Build the VideoRequest
        data = context.user_data
        request = VideoRequest(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            mode=data.get("mode", "image_to_video"),
            model=data.get("model", "veo_3"),
            duration=data.get("duration", 30),
            language=lang,
            text_prompt=data.get("text_prompt", ""),
            image_path=data.get("image_path"),
            url=data.get("url"),
            num_segments=data.get("num_segments", 1),
        )

        # Send initial progress message
        status_msg = await query.edit_message_text(
            get_message("analyzing_image", lang) if request.image_path
            else get_message("generating_script", lang, segments=request.num_segments),
            parse_mode=ParseMode.MARKDOWN,
        )

        # Register active job
        progress = GenerationProgress(
            request=request,
            status_message_id=status_msg.message_id,
            total_segments=request.num_segments,
        )
        self._active_jobs[request.user_id] = progress

        # Run generation pipeline (fire-and-forget with error handling)
        asyncio.create_task(
            self._run_generation(query.message.chat_id, request, progress, context)
        )

        return GENERATING

    # ─────────────────────────────────────────────────────────
    # Generation pipeline
    # ─────────────────────────────────────────────────────────

    async def _run_generation(
        self,
        chat_id: int,
        request: VideoRequest,
        progress: GenerationProgress,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Run the full video generation pipeline asynchronously."""
        lang = request.language
        bot = context.bot
        start_time = time.time()

        try:
            orchestrator = self._get_orchestrator()

            # Progress callback to update status message
            async def update_progress(segment: int, total: int, model: str, prompt: str, eta: str):
                if progress.is_cancelled:
                    raise asyncio.CancelledError("Generation cancelled by user")
                progress.current_segment = segment
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress.status_message_id,
                        text=get_message(
                            "generating", lang,
                            segment=segment,
                            total=total,
                            model=model,
                            duration=request.duration,
                            segment_prompt=prompt[:60] + "..." if len(prompt) > 60 else prompt,
                            eta=eta,
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass  # Message edit can fail if content unchanged

            async def update_status(msg_key: str, **kwargs):
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress.status_message_id,
                        text=get_message(msg_key, lang, **kwargs),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

            # Run generation
            result = await orchestrator.generate(
                request,
                progress_callback=update_progress,
                status_callback=update_status,
            )

            if progress.is_cancelled:
                return

            # Compute elapsed time
            elapsed_secs = int(time.time() - start_time)
            elapsed_str = f"{elapsed_secs // 60}m {elapsed_secs % 60}s"

            # Send completion message
            final_text = get_message(
                "complete", lang,
                model=get_model_name(request.model),
                duration=request.duration,
                segments=request.num_segments,
                elapsed=elapsed_str,
                filename=Path(result.video_path).name,
            )

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress.status_message_id,
                text=final_text,
                parse_mode=ParseMode.MARKDOWN,
            )

            # Send the video file
            video_path = Path(result.video_path)
            if video_path.exists():
                file_size = video_path.stat().st_size
                max_size = self.config.get("video", {}).get("telegram_max_size", 52_428_800)

                if file_size <= max_size:
                    with open(video_path, "rb") as video_file:
                        await bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            caption=f"UGC Video | {get_model_name(request.model)} | {request.duration}s",
                            supports_streaming=True,
                            width=720,
                            height=1280,
                        )
                else:
                    # File too large for Telegram — send as document
                    with open(video_path, "rb") as video_file:
                        await bot.send_document(
                            chat_id=chat_id,
                            document=video_file,
                            caption=f"UGC Video (large file) | {get_model_name(request.model)} | {request.duration}s",
                        )

            # Google Drive upload (if configured)
            if result.drive_link:
                await bot.send_message(
                    chat_id=chat_id,
                    text=get_message("drive_complete", lang, link=result.drive_link),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False,
                )

        except asyncio.CancelledError:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message("cancel", lang),
            )
        except Exception as e:
            logger.exception(f"Generation failed for user {request.user_id}: {e}")
            error_text = get_message("error", lang, error=str(e)[:200])
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress.status_message_id,
                    text=error_text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                await bot.send_message(chat_id=chat_id, text=error_text, parse_mode=ParseMode.MARKDOWN)
        finally:
            # Clean up job tracking
            self._active_jobs.pop(request.user_id, None)
            # Clean up downloaded input image
            if request.image_path and Path(request.image_path).exists():
                try:
                    os.unlink(request.image_path)
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────
    # Fallback handlers
    # ─────────────────────────────────────────────────────────

    async def fallback_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unexpected messages during conversation."""
        lang = self._get_user_lang(context)
        await update.message.reply_text(get_message("unknown_command", lang))

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global error handler."""
        logger.error(f"Update error: {context.error}", exc_info=context.error)

    # ─────────────────────────────────────────────────────────
    # Application setup and run
    # ─────────────────────────────────────────────────────────

    def build_application(self) -> Application:
        """Build and configure the Telegram Application."""
        app = (
            Application.builder()
            .token(self.bot_token)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )

        # ConversationHandler — the main interaction flow
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.cmd_start)],
            states={
                SELECT_MODE: [
                    CallbackQueryHandler(self.step_select_mode, pattern=r"^mode:"),
                ],
                SELECT_MODEL: [
                    CallbackQueryHandler(self.step_select_model, pattern=r"^model:"),
                ],
                SELECT_DURATION: [
                    CallbackQueryHandler(self.step_select_duration, pattern=r"^dur:"),
                ],
                CUSTOM_DURATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.step_custom_duration),
                    # Also allow button press if user clicked "Use nearest" hint
                    CallbackQueryHandler(self.step_select_duration, pattern=r"^dur:"),
                ],
                SELECT_LANGUAGE: [
                    CallbackQueryHandler(self.step_select_language, pattern=r"^lang:"),
                ],
                SEND_CONTENT: [
                    MessageHandler(filters.PHOTO, self.step_receive_photo),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.step_receive_text),
                ],
                AWAIT_IMAGE_AFTER_URL: [
                    MessageHandler(filters.PHOTO, self.step_receive_photo_after_url),
                ],
                ASK_DESCRIPTION: [
                    CallbackQueryHandler(self.step_ask_description, pattern=r"^desc:"),
                ],
                INPUT_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.step_input_description),
                ],
                CONFIRM_GENERATION: [
                    CallbackQueryHandler(self.step_confirm_generation, pattern=r"^confirm:"),
                ],
                GENERATING: [
                    # User can cancel even during generation
                    CommandHandler("cancel", self.cmd_cancel),
                    MessageHandler(filters.ALL, self.fallback_unknown),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cmd_cancel),
                CommandHandler("start", self.cmd_start),
            ],
            allow_reentry=True,
            conversation_timeout=3600,  # 1 hour timeout
        )

        # Register handlers
        app.add_handler(conv_handler)
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("status", self.cmd_status))

        # Global error handler
        app.add_error_handler(self.error_handler)

        return app

    async def run(self) -> None:
        """Start the bot with polling."""
        app = self.build_application()

        logger.info("Bot starting — polling for updates...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        # Keep running until interrupted
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("Bot shutting down...")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
