"""
web/routes_video.py
===================
Video generation routes.

Endpoints:
  POST /api/video/generate/ugc  — NEW UGC pipeline (primary)
  POST /api/video/generate      — Legacy pipeline (backward compat)
  GET  /api/video/tasks         — List tasks
  GET  /api/video/tasks/{id}    — Task detail
  GET  /api/video/tasks/{id}/timeline  — Timeline + segment status
  DELETE /api/video/tasks/{id}  — Soft delete
  GET  /api/video/download/{id} — Download final video
  GET  /api/presets             — Persona / platform / style presets
  POST /api/presenters/upload   — Upload presenter image/video
"""
from __future__ import annotations
import asyncio, math, os, shutil, uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import get_current_user
from web.database import get_db
from web.models_db import (
    AssetType, TaskAsset, TaskSegment, TaskStatus, TaskType,
    User, VideoTask
)
from web.schemas import (
    MessageResponse, PresetListResponse, TaskCreatedResponse,
    TaskTimelineResponse, TimelineSegmentResponse,
    UGCGenerateRequest, VideoGenerateRequest, VideoTaskList, VideoTaskResponse,
)
from web.tasks import run_ugc_generation_task, run_video_generation
from utils.logger import get_logger
from sqlalchemy import select, func as sqlfunc

logger = get_logger(__name__)
router = APIRouter(prefix="/api/video", tags=["video"])

# ── Config helpers ────────────────────────────────────────────────────────────

def _get_config() -> dict:
    from web.app import _APP_CONFIG
    return _APP_CONFIG

def _upload_dir() -> Path:
    return Path(_get_config().get("web", {}).get("upload_dir", "/app/data/uploads"))

def _video_dir() -> Path:
    return Path(_get_config().get("web", {}).get("video_dir", "/app/data/videos"))

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_IMAGE_SIZE_MB = 20
MAX_VIDEO_SIZE_MB = 200


async def _save_upload(upload: UploadFile, dest_dir: Path, prefix: str = "") -> str:
    """Save UploadFile, return filename."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(upload.filename or "file.bin").suffix.lower()
    fname = f"{prefix}{uuid.uuid4().hex}{ext}"
    dest = dest_dir / fname
    with open(dest, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            f.write(chunk)
    return fname


# ════════════════════════════════════════════════════════════════════════════════
# POST /api/video/generate/ugc  — New UGC pipeline
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/generate/ugc", response_model=TaskCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_ugc_video(
    # ── Product assets ────────────────────────────────────────────────────────
    primary_image: Optional[UploadFile] = File(default=None, description="Main product image"),
    gallery_images: list[UploadFile] = File(default=[], description="Product gallery (detail shots)"),
    usage_images: list[UploadFile] = File(default=[], description="Usage/context images"),
    # ── Presenter assets ──────────────────────────────────────────────────────
    presenter_image: Optional[UploadFile] = File(default=None, description="Presenter face photo"),
    presenter_video: Optional[UploadFile] = File(default=None, description="Presenter reference video"),
    # ── Text / JSON params ────────────────────────────────────────────────────
    duration: int = Form(default=30),
    language: str = Form(default="it"),
    aspect_ratio: str = Form(default="9:16"),
    quality_tier: str = Form(default="economy"),
    model: str = Form(default="auto"),
    platform: str = Form(default="douyin"),
    product_description: Optional[str] = Form(default=None),
    brand_name: Optional[str] = Form(default=None),
    product_url: Optional[str] = Form(default=None),
    selling_points: Optional[str] = Form(default=None),
    target_audience: Optional[str] = Form(default=None),
    persona_template: str = Form(default="energetic_female"),
    voice_preset: Optional[str] = Form(default=None),
    voice_id: Optional[str] = Form(default=None),
    hook_style: str = Form(default="result_first"),
    tone_style: str = Form(default="authentic_friend"),
    cta_style: str = Form(default="link_in_bio"),
    video_goal: str = Form(default="brand_awareness"),
    use_bgm: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a full UGC video production job.
    Accepts product images, optional presenter image/video, and all creative params.
    """
    upload_dir = _upload_dir()
    task_id = str(uuid.uuid4())

    # ── Validate and save primary image ──────────────────────────────────────
    if not primary_image:
        raise HTTPException(status_code=400, detail="primary_image is required for UGC pipeline")
    if primary_image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid image type: {primary_image.content_type}")

    primary_fname = await _save_upload(primary_image, upload_dir, "primary_")

    # ── Save gallery images ───────────────────────────────────────────────────
    gallery_fnames: list[str] = []
    for img in (gallery_images or [])[:8]:
        if img and img.content_type in ALLOWED_IMAGE_TYPES:
            gallery_fnames.append(await _save_upload(img, upload_dir, "gallery_"))

    # ── Save usage images ─────────────────────────────────────────────────────
    usage_fnames: list[str] = []
    for img in (usage_images or [])[:4]:
        if img and img.content_type in ALLOWED_IMAGE_TYPES:
            usage_fnames.append(await _save_upload(img, upload_dir, "usage_"))

    # ── Save presenter image ──────────────────────────────────────────────────
    presenter_fname: Optional[str] = None
    if presenter_image and presenter_image.content_type in ALLOWED_IMAGE_TYPES:
        presenter_fname = await _save_upload(presenter_image, upload_dir, "presenter_")

    # ── Save presenter video ──────────────────────────────────────────────────
    presenter_video_fname: Optional[str] = None
    if presenter_video and presenter_video.content_type in ALLOWED_VIDEO_TYPES:
        presenter_video_fname = await _save_upload(presenter_video, upload_dir, "presvid_")

    # ── Create VideoTask ──────────────────────────────────────────────────────
    task = VideoTask(
        id=task_id,
        user_id=current_user.id,
        task_type=TaskType.ugc,
        status=TaskStatus.pending,
        mode="ugc_video",
        model=model,
        duration=duration,
        language=language,
        aspect_ratio=aspect_ratio,
        quality_tier=quality_tier,
        image_filename=primary_fname,
        url=product_url,
        product_description=product_description,
        brand_name=brand_name,
        selling_points=selling_points,
        target_audience=target_audience,
        presenter_image_filename=presenter_fname,
        presenter_video_filename=presenter_video_fname,
        persona_template=persona_template,
        voice_preset=voice_preset,
        voice_id=voice_id,
        platform=platform,
        hook_style=hook_style,
        tone_style=tone_style,
        cta_style=cta_style,
        video_goal=video_goal,
        use_lipsync=bool(presenter_fname),
        use_bgm=use_bgm,
    )
    db.add(task)

    # ── Create TaskAsset records ──────────────────────────────────────────────
    assets = [TaskAsset(task_id=task_id, asset_type=AssetType.product_primary, filename=primary_fname, sort_order=0)]
    for i, fname in enumerate(gallery_fnames):
        assets.append(TaskAsset(task_id=task_id, asset_type=AssetType.product_gallery, filename=fname, sort_order=i))
    for i, fname in enumerate(usage_fnames):
        assets.append(TaskAsset(task_id=task_id, asset_type=AssetType.product_usage, filename=fname, sort_order=i))
    if presenter_fname:
        assets.append(TaskAsset(task_id=task_id, asset_type=AssetType.presenter_image, filename=presenter_fname, sort_order=0))
    if presenter_video_fname:
        assets.append(TaskAsset(task_id=task_id, asset_type=AssetType.presenter_video, filename=presenter_video_fname, sort_order=0))

    for a in assets:
        db.add(a)

    await db.commit()
    logger.info(f"UGC task created: {task_id}, primary={primary_fname}, gallery={len(gallery_fnames)}")

    # ── Launch pipeline ───────────────────────────────────────────────────────
    config = _get_config()
    asyncio.create_task(
        run_ugc_generation_task(task_id, config, current_user.numeric_id)
    )

    return TaskCreatedResponse(task_id=task_id, message="UGC video production started")




@router.get("/publish-queue")
async def list_publish_queue(
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    from core.publish_queue import PublishQueue
    queue = PublishQueue(_get_config())
    return {"items": queue.list(limit=limit, status=status_filter), "count": len(queue.list(limit=limit, status=status_filter))}


@router.post("/tasks/{task_id}/publish-queue")
async def enqueue_task_publish(
    task_id: str,
    platform: Optional[str] = None,
    scheduled_at: Optional[float] = None,
    priority: str = "normal",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.qa_report_json:
        raise HTTPException(status_code=400, detail="Task has no publish preparation yet")
    publish_package = task.qa_report_json.get("publish_preparation") or {}
    from core.platform_publish_adapter import PlatformPublishAdapter
    from core.publish_queue import PublishQueue
    from core.platform_resource_center import PlatformResourceCenter
    from core.platform_credential_center import PlatformCredentialCenter
    payload = PlatformPublishAdapter().build_payload(
        platform=platform or task.platform or "douyin",
        publish_package=publish_package,
        final_video_path=str(_video_dir() / task.result_filename) if task.result_filename else None,
        subtitle_path=str(_video_dir() / task.subtitle_filename) if task.subtitle_filename else None,
        task_id=task_id,
    )
    entry = PublishQueue(_get_config()).enqueue(
        task_id=task_id,
        platform=payload.platform,
        payload=payload.to_dict(),
        priority=priority,
        scheduled_at=scheduled_at,
        review_state=(task.qa_report_json or {}).get("review_state", {}).get("state", "draft"),
    )
    resource_bundle = PlatformResourceCenter(_get_config()).build_resource_bundle(payload.platform, publish_package)
    credential_context = PlatformCredentialCenter(_get_config()).build_publish_auth_context(payload.platform)
    task.qa_report_json["platform_publish_payload"] = payload.to_dict()
    task.qa_report_json["platform_resource_bundle"] = resource_bundle
    task.qa_report_json["platform_credential_context"] = credential_context
    task.qa_report_json["publish_queue"] = entry
    await db.commit()
    return {"task_id": task_id, "queue": entry, "credential_context": credential_context}


@router.get("/tasks/{task_id}/publish-package")
async def get_task_publish_package(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    payload = (task.qa_report_json or {}).get("platform_publish_payload")
    prep = (task.qa_report_json or {}).get("publish_preparation")
    queue = (task.qa_report_json or {}).get("publish_queue")
    return {"task_id": task_id, "publish_preparation": prep, "platform_publish_payload": payload, "publish_queue": queue}


@router.get("/tasks/{task_id}/review-state")
async def get_task_review_state(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    review = (task.qa_report_json or {}).get("review_state") or {"status": "draft", "history": []}
    return {"task_id": task_id, "review_state": review}


@router.post("/tasks/{task_id}/review-state")
async def transition_task_review_state(
    task_id: str,
    new_status: str,
    note: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    from core.review_state_machine import ReviewStateMachine
    machine = ReviewStateMachine()
    try:
        review = machine.transition((task.qa_report_json or {}).get("review_state"), new_status=new_status, actor=current_user.username, note=note or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    task.qa_report_json = dict(task.qa_report_json or {})
    task.qa_report_json["review_state"] = review
    publish_queue_info = (task.qa_report_json or {}).get("publish_queue") or {}
    queue_id = publish_queue_info.get("queue_id")
    if queue_id:
        from core.publish_queue import PublishQueue
        PublishQueue(_get_config()).update_status(queue_id, status=publish_queue_info.get("status", "queued"), extra={"review_state": review.get("status", "draft")})
    await db.commit()
    return {"task_id": task_id, "review_state": review}


@router.post("/tasks/{task_id}/publish-direct")
async def prepare_direct_publish(
    task_id: str,
    platform: Optional[str] = None,
    dry_run: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    payload = (task.qa_report_json or {}).get("platform_publish_payload")
    if not payload:
        raise HTTPException(status_code=400, detail="Task has no platform publish payload")
    from core.direct_publish_skeleton import DirectPublishSkeleton
    attempt = DirectPublishSkeleton().build_attempt(
        task_id=task_id,
        platform=platform or payload.get("platform") or task.platform or "douyin",
        publish_payload=payload,
        dry_run=dry_run,
    )
    task.qa_report_json = dict(task.qa_report_json or {})
    task.qa_report_json["direct_publish_attempt"] = attempt.to_dict()
    await db.commit()
    return {"task_id": task_id, "direct_publish_attempt": attempt.to_dict()}


# ════════════════════════════════════════════════════════════════════════════════
# POST /api/video/generate  — Legacy pipeline (backward compat)
# ════════════════════════════════════════════════════════════════════════════════



@router.get("/platform-credentials")
async def get_platform_credentials(
    platform: Optional[str] = None,
    reveal: bool = False,
    current_user: User = Depends(get_current_user),
):
    from core.platform_credential_center import PlatformCredentialCenter
    center = PlatformCredentialCenter(_get_config())
    if platform:
        return {
            "platform": platform,
            "credentials": center.get_platform(platform, masked=not reveal),
            "auth_context": center.build_publish_auth_context(platform),
        }
    return {
        "credentials": center.get_all(masked=not reveal),
        "platform_status": {
            name: center.build_publish_auth_context(name)
            for name in ["douyin", "xiaohongshu", "tiktok", "youtube"]
        },
    }


@router.post("/platform-credentials")
async def update_platform_credentials(
    platform: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    from core.platform_credential_center import PlatformCredentialCenter
    center = PlatformCredentialCenter(_get_config())
    updated = center.update_platform(platform, payload)
    return {"platform": platform, "credentials": updated, "auth_context": center.build_publish_auth_context(platform)}


@router.get("/publish-queue/due")
async def list_due_publish_queue(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    from core.publish_queue import PublishQueue
    items = PublishQueue(_get_config()).list_due(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/publish-queue/{queue_id}/reschedule")
async def reschedule_publish_queue_entry(
    queue_id: str,
    scheduled_at: float,
    note: str = "",
    current_user: User = Depends(get_current_user),
):
    from core.publish_queue import PublishQueue
    updated = PublishQueue(_get_config()).reschedule(queue_id, scheduled_at=scheduled_at, note=note)
    if not updated:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return {"queue": updated}


@router.get("/platform-resources")
async def get_platform_resources(
    platform: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    from core.platform_resource_center import PlatformResourceCenter
    center = PlatformResourceCenter(_get_config())
    if platform:
        return {"platform": platform, "resource": center.get_platform(platform)}
    return center.get_all()


@router.post("/platform-resources")
async def update_platform_resources(
    platform: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    from core.platform_resource_center import PlatformResourceCenter
    center = PlatformResourceCenter(_get_config())
    updated = center.update_platform(platform, payload)
    return {"platform": platform, "resource": updated}


@router.get("/publish-queue/{queue_id}")
async def get_publish_queue_entry(
    queue_id: str,
    current_user: User = Depends(get_current_user),
):
    from core.publish_queue import PublishQueue
    item = PublishQueue(_get_config()).get(queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return {"queue": item}


@router.post("/publish-queue/{queue_id}/retry")
async def retry_publish_queue_entry(
    queue_id: str,
    note: Optional[str] = None,
    dry_run: bool = True,
    current_user: User = Depends(get_current_user),
):
    from core.publish_retry_engine import PublishRetryEngine
    try:
        result = PublishRetryEngine(_get_config()).retry(queue_id, dry_run=dry_run, note=note or "")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result




@router.post("/publish-queue/{queue_id}/execute")
async def execute_publish_queue_entry(
    queue_id: str,
    dry_run: bool = True,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from core.publish_task_executor import PublishTaskExecutor
    from sqlalchemy import select
    try:
        result = PublishTaskExecutor(_get_config()).execute(
            queue_id,
            dry_run=dry_run,
            actor=getattr(current_user, "email", None) or getattr(current_user, "username", "user"),
            force=force,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = (result.get("queue_entry") or {}).get("task_id")
    if task_id:
        stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
        task = (await db.execute(stmt)).scalar_one_or_none()
        if task:
            qa = dict(task.qa_report_json or {})
            qa["publish_execution"] = result.get("attempt")
            qa["platform_receipt"] = result.get("receipt")
            qa["publish_queue"] = result.get("queue_entry")
            task.qa_report_json = qa
            await db.commit()
    return result


@router.get("/publish-receipts")
async def list_publish_receipts(
    task_id: Optional[str] = None,
    queue_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    from core.platform_receipt_recorder import PlatformReceiptRecorder
    items = PlatformReceiptRecorder(_get_config()).list(task_id=task_id, queue_id=queue_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/tasks/{task_id}/publish-receipts")
async def get_task_publish_receipts(
    task_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(VideoTask).where(VideoTask.id == task_id, VideoTask.user_id == current_user.id, VideoTask.is_deleted.is_(False))
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    from core.platform_receipt_recorder import PlatformReceiptRecorder
    items = PlatformReceiptRecorder(_get_config()).list(task_id=task_id, limit=limit)
    return {"task_id": task_id, "items": items, "count": len(items)}


@router.post("/generate", response_model=TaskCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_video_legacy(
    image: Optional[UploadFile] = File(default=None),
    mode: str = Form(default="image_to_video"),
    model: str = Form(default="auto"),
    duration: int = Form(default=15),
    language: str = Form(default="it"),
    aspect_ratio: str = Form(default="9:16"),
    text_prompt: Optional[str] = Form(default=None),
    url: Optional[str] = Form(default=None),
    quality_tier: str = Form(default="economy"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy generation endpoint — routes to original pipeline."""
    upload_dir = _upload_dir()
    task_id = str(uuid.uuid4())

    image_fname: Optional[str] = None
    if image:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid image type: {image.content_type}")
        image_fname = await _save_upload(image, upload_dir)

    task = VideoTask(
        id=task_id,
        user_id=current_user.id,
        task_type=TaskType.legacy,
        status=TaskStatus.pending,
        mode=mode,
        model=model,
        duration=duration,
        language=language,
        aspect_ratio=aspect_ratio,
        quality_tier=quality_tier,
        text_prompt=text_prompt,
        image_filename=image_fname,
        url=url,
    )
    db.add(task)
    await db.commit()

    config = _get_config()
    asyncio.create_task(run_video_generation(task_id, config, current_user.numeric_id))

    return TaskCreatedResponse(task_id=task_id, message="Video generation started")


# ════════════════════════════════════════════════════════════════════════════════
# POST /api/presenters/upload
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/presenters/upload", response_model=dict)
async def upload_presenter(
    presenter_image: Optional[UploadFile] = File(default=None),
    presenter_video: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
):
    """Upload a presenter image or video for use in future UGC tasks."""
    upload_dir = _upload_dir() / "presenters"
    result = {}
    if presenter_image and presenter_image.content_type in ALLOWED_IMAGE_TYPES:
        fname = await _save_upload(presenter_image, upload_dir, "pimg_")
        result["presenter_image_filename"] = fname
    if presenter_video and presenter_video.content_type in ALLOWED_VIDEO_TYPES:
        fname = await _save_upload(presenter_video, upload_dir, "pvid_")
        result["presenter_video_filename"] = fname
    if not result:
        raise HTTPException(status_code=400, detail="No valid file provided")
    return result


# ════════════════════════════════════════════════════════════════════════════════
# GET /api/presets
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/presets", response_model=dict)
async def get_presets():
    """Return all dropdown presets for the UGC form."""
    from core.director_knowledge_base import PERSONA_TEMPLATES, PLATFORM_PRESETS, HOOK_TEMPLATES

    personas = [
        {"key": k, "name": v["name"], "description": v["description"], "voice_preset": v["voice_preset"]}
        for k, v in PERSONA_TEMPLATES.items()
    ]
    platforms = [
        {"key": k, "name": v["name"], "aspect_ratio": v["aspect_ratio"],
         "max_duration": v["max_duration"], "description": f"Optimal {v['optimal_duration']}s"}
        for k, v in PLATFORM_PRESETS.items()
    ]
    hooks = [{"key": k, "name": v["name"], "description": v["description"]} for k, v in HOOK_TEMPLATES.items()]
    tone_styles = [
        {"key": "authentic_friend",    "name": "闺蜜推荐"},
        {"key": "professional_expert", "name": "专业讲解"},
        {"key": "energetic_hype",      "name": "高能种草"},
        {"key": "luxury_aspirational", "name": "高奢向往"},
        {"key": "funny_relatable",     "name": "搞笑接地气"},
    ]
    cta_styles = [
        {"key": "link_in_bio",   "name": "主页链接"},
        {"key": "buy_now",       "name": "立即购买"},
        {"key": "limited_offer", "name": "限时优惠"},
        {"key": "follow_for_more","name": "关注更多"},
        {"key": "comment_below", "name": "评论区见"},
    ]
    return {
        "personas": personas,
        "platforms": platforms,
        "hook_styles": hooks,
        "tone_styles": tone_styles,
        "cta_styles": cta_styles,
    }


# ════════════════════════════════════════════════════════════════════════════════
# Task listing / detail
# ════════════════════════════════════════════════════════════════════════════════

@router.get("/tasks", response_model=VideoTaskList)
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    stmt = (
        select(VideoTask)
        .where(VideoTask.user_id == current_user.id, VideoTask.is_deleted == False)
        .order_by(VideoTask.created_at.desc())
        .offset(offset).limit(page_size)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    count_stmt = select(sqlfunc.count()).select_from(VideoTask).where(
        VideoTask.user_id == current_user.id, VideoTask.is_deleted == False
    )
    total = (await db.execute(count_stmt)).scalar() or 0
    pages = math.ceil(total / page_size) if total else 1

    return VideoTaskList(items=tasks, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/tasks/{task_id}", response_model=VideoTaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.id)
    return task


@router.get("/tasks/{task_id}/timeline", response_model=TaskTimelineResponse)
async def get_task_timeline(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.id)
    if not task.timeline_json:
        raise HTTPException(status_code=404, detail="Timeline not yet available")

    stmt = select(TaskSegment).where(TaskSegment.task_id == task_id).order_by(TaskSegment.segment_index)
    result = await db.execute(stmt)
    segments = result.scalars().all()

    segs_resp = [
        TimelineSegmentResponse(
            id=s.id, task_id=s.task_id, segment_index=s.segment_index,
            track_type=s.track_type, duration=s.duration,
            spoken_line=s.spoken_line, overlay_text=s.overlay_text,
            status=s.status.value, output_asset_id=s.output_asset_id,
        )
        for s in segments
    ]

    tl = task.timeline_json
    return TaskTimelineResponse(
        task_id=task_id,
        total_duration=sum(s.duration for s in segs_resp),
        segments=segs_resp,
        strategy=tl.get("strategy"),
        platform=tl.get("platform"),
        persona=tl.get("persona"),
    )


@router.delete("/tasks/{task_id}", response_model=MessageResponse)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.id)
    task.is_deleted = True
    await db.commit()
    return MessageResponse(message="Task deleted")


@router.get("/download/{task_id}")
async def download_video(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_task_or_404(db, task_id, current_user.id)
    if task.status != TaskStatus.completed or not task.result_filename:
        raise HTTPException(status_code=404, detail="Video not ready")
    path = _video_dir() / task.result_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(path, media_type="video/mp4", filename=task.result_filename)


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_task_or_404(db: AsyncSession, task_id: str, user_id: str) -> VideoTask:
    stmt = select(VideoTask).where(
        VideoTask.id == task_id,
        VideoTask.user_id == user_id,
        VideoTask.is_deleted == False,
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
