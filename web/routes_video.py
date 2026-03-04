"""
web/routes_video.py
===================
Video generation API router for UGC Video Pro.

Endpoints:
    POST   /generate          — submit a video generation job (multipart form)
    GET    /tasks             — list current user's tasks (paginated)
    GET    /tasks/{task_id}   — single task detail
    GET    /download/{task_id} — stream video file download
    DELETE /tasks/{task_id}   — soft-delete task and remove files
"""

import asyncio
import logging
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import get_current_user
from web.database import get_db
from web.models_db import TaskStatus, User, VideoTask
from web.schemas import (
    MessageResponse,
    TaskCreatedResponse,
    VideoGenerateRequest,
    VideoTaskList,
    VideoTaskResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])


def _get_config() -> dict:
    """Lazily retrieve the app config to avoid circular imports at module load."""
    from web.app import get_app_config  # noqa: PLC0415
    return get_app_config()


# ── Storage paths ───────────────────────────────────────────────────────────────────

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/app/data"))
UPLOADS_DIR = DATA_ROOT / "uploads"
VIDEOS_DIR = DATA_ROOT / "videos"
MAX_IMAGE_SIZE_MB = 20


# ── POST /generate ──────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a video generation job",
)
async def generate_video(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    # --- multipart form fields ---
    mode: str = Form(..., pattern="^(text_to_video|image_to_video|url_to_video)$"),
    model: str = Form(..., pattern="^(sora_2|sora_2_pro|seedance_2|veo_3|veo_3_pro|veo_31_pro)$"),
    duration: int = Form(..., ge=4, le=600),
    language: str = Form(default="en", pattern="^(zh|en|it)$"),
    aspect_ratio: str = Form(default="9:16", pattern="^(9:16|16:9)$"),
    text_prompt: Optional[str] = Form(default=None),
    url: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
) -> TaskCreatedResponse:
    """
    Accept a multipart/form-data request containing generation parameters and
    (optionally) an uploaded product image.  Creates a VideoTask in the
    database, then launches the generation pipeline in the background.

    Returns:
        task_id — the UUID of the created VideoTask
    """
    # ── Validate mode-specific requirements ────────────────────────────────────────────
    if mode == "text_to_video" and not text_prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="text_prompt is required for text_to_video mode",
        )
    if mode in ("image_to_video", "url_to_video") and image is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"image file is required for {mode} mode",
        )
    if mode == "url_to_video" and not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="url is required for url_to_video mode",
        )

    # ── Save uploaded image ───────────────────────────────────────────────────────────────
    image_filename: Optional[str] = None
    if image is not None:
        # Validate size (read first chunk to check content type)
        img_bytes = await image.read()
        if len(img_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image exceeds maximum size of {MAX_IMAGE_SIZE_MB} MB",
            )

        # Determine file extension
        orig_name = image.filename or "upload.jpg"
        ext = Path(orig_name).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only JPG, PNG and WebP images are supported",
            )

        # Build per-user upload directory
        ts = int(datetime.now(timezone.utc).timestamp())
        user_upload_dir = UPLOADS_DIR / current_user.id
        user_upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{ts}_{Path(orig_name).stem[:50]}{ext}"
        dest_path = user_upload_dir / safe_name

        dest_path.write_bytes(img_bytes)
        # Store relative path: uploads/{user_id}/{filename}
        image_filename = f"uploads/{current_user.id}/{safe_name}"
        logger.debug(f"Image saved: {dest_path} ({len(img_bytes)} bytes)")

    # ── Create VideoTask in database ──────────────────────────────────────────────────────
    task = VideoTask(
        user_id=current_user.id,
        status=TaskStatus.pending,
        mode=mode,
        model=model,
        duration=duration,
        language=language,
        aspect_ratio=aspect_ratio,
        text_prompt=text_prompt,
        image_filename=image_filename,
        url=url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    task_id = task.id
    logger.info(
        f"VideoTask created: {task_id} user={current_user.email} "
        f"mode={mode} model={model} duration={duration}s"
    )

    # ── Launch background generation ─────────────────────────────────────────────────────
    # Import lazily to avoid circular imports at module load time
    from web.tasks import run_video_generation

    # Build a minimal config for the orchestrator.
    # _get_config() lazily imports from app.py to avoid circular imports.
    config = _get_config()

    asyncio.create_task(
        run_video_generation(task_id=task_id, config=config, user_numeric_id=current_user.numeric_id)
    )

    return TaskCreatedResponse(task_id=task_id)


# ── GET /tasks ─────────────────────────────────────────────────────────────────────

@router.get(
    "/tasks",
    response_model=VideoTaskList,
    summary="List the current user's video tasks (newest first)",
)
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> VideoTaskList:
    """Return a paginated list of the authenticated user's VideoTasks."""
    offset = (page - 1) * page_size

    # Total count
    total_result = await db.execute(
        select(func.count(VideoTask.id)).where(
            VideoTask.user_id == current_user.id,
            VideoTask.is_deleted.is_(False),
        )
    )
    total: int = total_result.scalar_one()

    # Page of tasks
    tasks_result = await db.execute(
        select(VideoTask)
        .where(
            VideoTask.user_id == current_user.id,
            VideoTask.is_deleted.is_(False),
        )
        .order_by(VideoTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    tasks = tasks_result.scalars().all()

    pages = math.ceil(total / page_size) if total > 0 else 1

    return VideoTaskList(
        items=[VideoTaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────────────

@router.get(
    "/tasks/{task_id}",
    response_model=VideoTaskResponse,
    summary="Get details of a single video task",
)
async def get_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VideoTaskResponse:
    """
    Return the full details of a VideoTask.

    Only the task owner or an admin may access this endpoint.
    """
    from web.models_db import UserRole

    task = await _get_task_or_404(task_id, db)

    if task.user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this task",
        )

    return VideoTaskResponse.model_validate(task)


# ── GET /download/{task_id} ──────────────────────────────────────────────────────────────

@router.get(
    "/download/{task_id}",
    summary="Download the generated video file",
)
async def download_video(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """
    Stream the completed video file for download.

    Raises:
        404: Task not found or video not yet generated
        403: Not the task owner (or admin)
    """
    from web.models_db import UserRole

    task = await _get_task_or_404(task_id, db)

    if task.user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to download this file",
        )

    if task.status != TaskStatus.completed or not task.result_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not yet available — check task status",
        )

    video_path = DATA_ROOT / task.result_filename
    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found on server",
        )

    filename = video_path.name
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── DELETE /tasks/{task_id} ─────────────────────────────────────────────────────────────

@router.delete(
    "/tasks/{task_id}",
    response_model=MessageResponse,
    summary="Soft-delete a task and remove its files",
)
async def delete_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Mark a VideoTask as deleted and remove associated files from disk.

    Only the task owner or an admin may delete a task.
    """
    from web.models_db import UserRole

    task = await _get_task_or_404(task_id, db)

    if task.user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this task",
        )

    # Remove video file
    if task.result_filename:
        video_path = DATA_ROOT / task.result_filename
        _safe_remove(video_path)

    # Remove uploaded image
    if task.image_filename:
        img_path = DATA_ROOT / task.image_filename
        _safe_remove(img_path)

    # Soft-delete
    task.is_deleted = True
    await db.commit()

    logger.info(f"Task {task_id} soft-deleted by user {current_user.email}")
    return MessageResponse(message="Task deleted successfully")


# ── Private helpers ───────────────────────────────────────────────────────────────────

async def _get_task_or_404(task_id: str, db: AsyncSession) -> VideoTask:
    """Fetch a non-deleted VideoTask or raise 404."""
    result = await db.execute(
        select(VideoTask).where(
            VideoTask.id == task_id,
            VideoTask.is_deleted.is_(False),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


def _safe_remove(path: Path) -> None:
    """Remove a file without raising if it doesn't exist."""
    try:
        if path.exists():
            path.unlink()
            logger.debug(f"Removed file: {path}")
    except Exception as exc:
        logger.warning(f"Could not remove {path}: {exc}")
