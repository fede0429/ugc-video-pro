"""
web/tasks.py
============
Background video generation task runner for UGC Video Pro.

This module bridges the FastAPI web layer with the existing
core.orchestrator.VideoOrchestrator pipeline (unchanged).

Entry point:
    asyncio.create_task(run_video_generation(task_id, config, user_numeric_id))

Flow:
    1. Load the VideoTask record from the database
    2. Build a VideoRequest for the orchestrator
    3. Hook progress_callback → broadcast WS updates + update DB progress
    4. Hook status_callback  → broadcast WS status messages
    5. On success: write result_filename, drive_link, status=completed
    6. On failure: write error_message, status=failed
    7. Always broadcast a final WS message so clients know to stop polling
"""

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from web.database import AsyncSessionLocal
from web.models_db import TaskStatus, VideoTask
from web.websocket import manager as ws_manager

logger = logging.getLogger(__name__)

# ── Storage paths (must mirror routes_video.py) ─────────────────────────────────────────────
DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/app/data"))
VIDEOS_DIR = DATA_ROOT / "videos"


# ── Main task runner ──────────────────────────────────────────────────────────────────

async def run_video_generation(
    task_id: str,
    config: dict,
    user_numeric_id: int,
) -> None:
    """
    Run the full video generation pipeline for the given task_id.

    Args:
        task_id:         UUID of the VideoTask row in the database
        config:          Application config dict passed to VideoOrchestrator
        user_numeric_id: Integer user identifier for VideoRequest.user_id
    """
    logger.info(f"[task={task_id}] Background generation starting")

    # ── Load task from database ─────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(VideoTask).where(VideoTask.id == task_id))
        task: Optional[VideoTask] = result.scalar_one_or_none()

        if task is None:
            logger.error(f"[task={task_id}] Task not found in database — aborting")
            return

        # Mark as processing
        task.status = TaskStatus.processing
        await db.commit()

    # Broadcast initial status
    await _broadcast_status(task_id, TaskStatus.processing.value)

    # ── Determine image path ─────────────────────────────────────────────────────────────
    image_path: Optional[str] = None
    if task.image_filename:
        full_img_path = DATA_ROOT / task.image_filename
        if full_img_path.exists():
            image_path = str(full_img_path)
        else:
            logger.warning(f"[task={task_id}] Image file not found: {full_img_path}")

    # ── Ensure output directory for this user ───────────────────────────────────────────
    user_video_dir = VIDEOS_DIR / task.user_id
    user_video_dir.mkdir(parents=True, exist_ok=True)

    # Override the orchestrator's output_dir to the user-specific directory
    task_config = dict(config)
    task_config.setdefault("video", {})
    task_config["video"] = dict(task_config.get("video", {}))
    task_config["video"]["output_dir"] = str(user_video_dir)

    # ── Build VideoRequest ─────────────────────────────────────────────────────────────
    from core.orchestrator import VideoOrchestrator, VideoRequest

    request = VideoRequest(
        user_id=user_numeric_id,
        chat_id=0,                       # Not used in web context
        mode=task.mode,
        model=task.model,
        duration=task.duration,
        language=task.language,
        aspect_ratio=task.aspect_ratio,
        text_prompt=task.text_prompt or "",
        image_path=image_path,
        url=task.url,
    )

    # ── Callbacks ──────────────────────────────────────────────────────────────────────

    async def progress_callback(
        segment: int,
        total: int,
        model: str,
        prompt: str,
        eta: str,
    ) -> None:
        """Called by frame_chainer for each completed segment."""
        logger.debug(f"[task={task_id}] Progress {segment}/{total}")

        # Persist to DB
        async with AsyncSessionLocal() as db2:
            res = await db2.execute(select(VideoTask).where(VideoTask.id == task_id))
            t = res.scalar_one_or_none()
            if t:
                t.progress_segment = segment
                t.progress_total = total
                await db2.commit()

        # Broadcast to WebSocket clients
        await ws_manager.broadcast(
            task_id,
            {
                "task_id": task_id,
                "event": "progress",
                "status": TaskStatus.processing.value,
                "segment": segment,
                "total": total,
                "message": f"Generating clip {segment}/{total} ({model}) — ETA {eta}",
            },
        )

    async def status_callback(msg_key: str, **kwargs) -> None:
        """Called by orchestrator for named status updates."""
        logger.debug(f"[task={task_id}] Status update: {msg_key}")

        # Try to get a localised message via bot.messages
        try:
            from bot.messages import get_message
            # Load language from current task (already have it in outer scope)
            lang = task.language if task.language else "en"
            human_message = get_message(msg_key, lang=lang, **kwargs)
        except Exception:
            human_message = msg_key

        await ws_manager.broadcast(
            task_id,
            {
                "task_id": task_id,
                "event": "message",
                "status": TaskStatus.processing.value,
                "message": human_message,
            },
        )

    # ── Run orchestrator ──────────────────────────────────────────────────────────────────
    orchestrator = VideoOrchestrator(task_config)

    try:
        video_result = await orchestrator.generate(
            request=request,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[task={task_id}] Generation failed: {error_msg}", exc_info=True)

        async with AsyncSessionLocal() as db3:
            res3 = await db3.execute(select(VideoTask).where(VideoTask.id == task_id))
            t3 = res3.scalar_one_or_none()
            if t3:
                t3.status = TaskStatus.failed
                t3.error_message = error_msg
                t3.completed_at = datetime.now(timezone.utc)
                await db3.commit()

        await ws_manager.broadcast(
            task_id,
            {
                "task_id": task_id,
                "event": "error",
                "status": TaskStatus.failed.value,
                "error": error_msg,
                "message": f"Generation failed: {error_msg}",
            },
        )
        return

    # ── Success: persist result ──────────────────────────────────────────────────────────────
    final_path = Path(video_result.video_path)
    # Store relative to DATA_ROOT
    try:
        rel_path = final_path.relative_to(DATA_ROOT)
        result_filename = str(rel_path)
    except ValueError:
        # If file is outside DATA_ROOT (e.g., /tmp), move it in
        dest = user_video_dir / final_path.name
        shutil.move(str(final_path), str(dest))
        result_filename = str(dest.relative_to(DATA_ROOT))

    async with AsyncSessionLocal() as db4:
        res4 = await db4.execute(select(VideoTask).where(VideoTask.id == task_id))
        t4 = res4.scalar_one_or_none()
        if t4:
            t4.status = TaskStatus.completed
            t4.result_filename = result_filename
            t4.result_drive_link = video_result.drive_link
            t4.progress_segment = video_result.num_segments
            t4.progress_total = video_result.num_segments
            t4.completed_at = datetime.now(timezone.utc)
            await db4.commit()

    logger.info(
        f"[task={task_id}] Completed: {result_filename} "
        f"({video_result.elapsed_seconds:.0f}s, {video_result.num_segments} clips)"
    )

    await ws_manager.broadcast(
        task_id,
        {
            "task_id": task_id,
            "event": "status",
            "status": TaskStatus.completed.value,
            "segment": video_result.num_segments,
            "total": video_result.num_segments,
            "result_filename": result_filename,
            "drive_link": video_result.drive_link,
            "message": (
                f"Video ready! {video_result.duration}s, "
                f"{video_result.num_segments} clips, "
                f"{video_result.elapsed_seconds:.0f}s elapsed"
            ),
        },
    )


# ── Private helpers ───────────────────────────────────────────────────────────────────

async def _broadcast_status(task_id: str, status_value: str) -> None:
    """Broadcast a simple status change event."""
    await ws_manager.broadcast(
        task_id,
        {
            "task_id": task_id,
            "event": "status",
            "status": status_value,
        },
    )
