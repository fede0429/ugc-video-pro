"""
web/tasks.py
============
Task executors. Two pipelines:

UGC Pipeline (blueprint-compliant, 17 stages):
    routes_video → FileStore save → ExtendedUGCVideoRequest
    → PresenterAnalyzer   → PresenterProfile
    → ImageAnalyzer       → ProductProfile
    → UGCProducer         → ProductionPlan
    → ScriptGenerator     → TimelineScript
    → TTSService          → AudioSegmentAsset[]
    → LipSyncService      → RenderedAsset[]  (A-roll)
    → BRollSequenceBuilder→ RenderedAsset[]  (B-roll)
    → SubtitleService     → captions.srt
    → OverlayService      → overlay_plan
    → TimelineComposer    → final_video.mp4
    → QAService           → QAReport
    → DB persist + WebSocket broadcast

Legacy Pipeline:
    Delegates unchanged to core/orchestrator.py
"""
from __future__ import annotations
import asyncio, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from web.database import AsyncSessionLocal
from web.models_db import (
    AssetType, SegmentStatus, TaskAsset, TaskSegment,
    TaskStatus, TaskType, VideoTask,
)
from web.websocket import broadcast_progress
from utils.logger import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# UGC PIPELINE
# ════════════════════════════════════════════════════════════════════════════════

async def run_ugc_generation_task(task_id: str, config: dict, user_numeric_id: int):
    async with AsyncSessionLocal() as db:
        stmt = select(VideoTask).where(VideoTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            logger.error(f"UGC task {task_id} not found")
            return
        task.status = TaskStatus.processing
        await db.commit()
        try:
            await _run_ugc(task, db, config)
        except Exception as e:
            logger.exception(f"UGC task {task_id} failed: {e}")
            task.status = TaskStatus.failed
            task.error_message = str(e)
            await db.commit()
            await broadcast_progress(task_id, {
                "task_id": task_id, "event": "error",
                "status": "failed", "error": str(e),
            })


async def _run_ugc(task: VideoTask, db, config: dict):
    task_id = task.id
    upload_dir = Path(config.get("web", {}).get("upload_dir", "/app/data/uploads"))
    video_dir  = Path(config.get("web", {}).get("video_dir",  "/app/data/videos"))

    async def _stage(stage: str, msg: str):
        await broadcast_progress(task_id, {
            "task_id": task_id, "event": "progress",
            "status": "processing", "stage": stage, "stage_message": msg,
        })
        logger.info(f"[{task_id}] ── {stage}: {msg}")

    # ── 1. FileStore ──────────────────────────────────────────────────────────
    await _stage("initializing", "Creating task directories...")
    from utils.file_store import FileStore
    file_store = FileStore(config)
    file_store.create_task_dirs(task_id)

    # ── 2. Load asset paths ───────────────────────────────────────────────────
    stmt = select(TaskAsset).where(TaskAsset.task_id == task_id)
    assets_db = list((await db.execute(stmt)).scalars().all())

    def _paths(atype: AssetType) -> list[str]:
        return [
            str(upload_dir / a.filename)
            for a in assets_db if a.asset_type == atype
            and (upload_dir / a.filename).exists()
        ]

    primary_paths  = _paths(AssetType.product_primary)
    gallery_paths  = _paths(AssetType.product_gallery)
    usage_paths    = _paths(AssetType.product_usage)
    presenter_imgs = _paths(AssetType.presenter_image)
    presenter_vids = _paths(AssetType.presenter_video)

    primary_image    = primary_paths[0] if primary_paths else None
    presenter_image  = presenter_imgs[0] if presenter_imgs else (
        str(upload_dir / task.presenter_image_filename)
        if task.presenter_image_filename and (upload_dir / task.presenter_image_filename).exists()
        else None
    )
    presenter_video  = presenter_vids[0] if presenter_vids else None

    # ── 3. Build ExtendedUGCVideoRequest ──────────────────────────────────────
    from core.timeline_types import ExtendedUGCVideoRequest
    request = ExtendedUGCVideoRequest.from_task_and_paths(
        task=task,
        primary_image=primary_image,
        gallery_images=gallery_paths,
        usage_images=usage_paths,
        presenter_image=presenter_image,
        presenter_video=presenter_video,
    )

    # ── 4. Product analysis ───────────────────────────────────────────────────
    await _stage("analyzing_product", "🔍 Analyzing product images...")
    from services.image_analyzer import ImageAnalyzer
    analyzer = ImageAnalyzer(config)
    all_product_paths = [p for p in [primary_image] + gallery_paths + usage_paths if p]
    product_profile = await analyzer.analyze_images(
        image_paths=all_product_paths,
        description=task.product_description,
    )
    if task.brand_name:     product_profile.brand = task.brand_name
    if task.target_audience: product_profile.target_audience = task.target_audience
    if task.selling_points:
        product_profile.selling_points = [s.strip() for s in task.selling_points.split(",") if s.strip()]

    task.product_profile_json = product_profile.to_dict()

    # ── 5. Presenter analysis ─────────────────────────────────────────────────
    await _stage("analyzing_presenter", "🎭 Building presenter profile...")
    from services.presenter_analyzer import PresenterAnalyzer
    pa = PresenterAnalyzer(config)
    presenter_profile = await pa.build_presenter_profile(
        presenter_image=presenter_image,
        presenter_video=presenter_video,
        persona_template=task.persona_template or "energetic_female",
        voice_preset=task.voice_preset,
        voice_id_override=task.voice_id,
        lipsync_model_override=task.lipsync_model,
    )
    task.presenter_profile_json = presenter_profile.to_dict()

    # ── 6. Production plan ────────────────────────────────────────────────────
    await _stage("planning_script", "🧠 Building production plan...")
    from core.director_agent import UGCProducer
    producer = UGCProducer(config)
    product_summary = (
        f"{product_profile.brand} {product_profile.description}. "
        f"Features: {', '.join(product_profile.key_features[:5])}. "
        f"Selling points: {', '.join(product_profile.selling_points[:5])}."
    )
    production_plan = await producer.build_plan(
        product_summary=product_summary,
        request=request,
        presenter_profile=presenter_profile,
    )
    variant_batch_report = {
        "selected_variant_id": production_plan.selected_variant_id,
        "selected_framework": production_plan.selected_framework,
        "variants": production_plan.variants,
        "reasoning": production_plan.reasoning,
    }

    # ── 7. Timeline script + multi-script batch selection ──────────────────────
    await _stage("generating_script", "📝 Generating UGC timeline script batch...")
    from core.script_generator import ScriptGenerator
    from core.multi_script_engine import MultiScriptBatchEngine
    from services.video_scoring_service import VideoScoringService
    sg = ScriptGenerator(config)
    batch_engine = MultiScriptBatchEngine(script_generator=sg, scorer=VideoScoringService())
    script_batch_report = await batch_engine.generate(
        request=request,
        product_profile=product_profile,
        presenter_profile=presenter_profile,
        production_plan=production_plan,
        max_scripts=int(getattr(request, "script_batch_size", 3) or 3),
    )
    from core.timeline_types import TimelineScript
    timeline = TimelineScript.from_dict(script_batch_report["selected_timeline"])
    creative_score = VideoScoringService().score(timeline, None)

    # ── 8. Persist timeline segments to DB ────────────────────────────────────
    for seg in timeline.segments:
        db_seg = TaskSegment(
            task_id=task_id,
            segment_index=seg.segment_index,
            segment_ref_id=seg.segment_id,
            track_type=seg.track_type,
            duration=float(seg.duration_seconds),
            spoken_line=seg.spoken_line,
            overlay_text=seg.overlay_text,
            b_roll_prompt=seg.b_roll_prompt,
            emotion=getattr(seg, "emotion", ""),
            shot_type=getattr(seg, "shot_type", ""),
            status=SegmentStatus.pending,
        )
        db.add(db_seg)

    task.timeline_json = {
        "strategy": production_plan.strategy,
        "platform": production_plan.platform,
        "persona": production_plan.persona,
        "total_duration": timeline.total_duration,
        "selected_variant_id": script_batch_report.get("selected_variant_id", production_plan.selected_variant_id),
        "selected_framework": production_plan.selected_framework,
        "variant_batch_report": variant_batch_report,
        "script_batch_report": {k: v for k, v in script_batch_report.items() if k != "selected_timeline"},
        "creative_score": creative_score.to_dict(),
    }
    await db.commit()

    # ── 9. TTS — PDF blueprint API ────────────────────────────────────────────
    await _stage("generating_voice", "🎙 Synthesizing voice segments...")
    from services.tts_service import TTSService
    tts = TTSService(config)
    language = request.language.split(",")[0]
    audio_assets = await tts.synthesize_segments(
        task_id=task_id,
        timeline=timeline,
        voice_preset=presenter_profile.voice_preset or language,
        language=language,
        file_store=file_store,
    )

    # ── 10. A-roll lipsync ────────────────────────────────────────────────────
    await _stage("generating_a_roll", "🎭 Rendering A-roll talking-head clips...")
    from services.lipsync_service import LipSyncService
    ls = LipSyncService(config)
    a_roll_assets = await ls.render_a_roll_segments(
        task_id, timeline, presenter_profile, audio_assets, file_store
    )

    # ── 11. B-roll — BRollSequenceBuilder ────────────────────────────────────
    await _stage("generating_b_roll", "🎬 Generating B-roll product clips...")
    from core.frame_chainer import BRollSequenceBuilder, VideoModelRouter
    router = VideoModelRouter(config)
    builder = BRollSequenceBuilder(
        video_model_router=router,
        file_store=file_store,
        config=config,
    )
    b_roll_assets = await builder.render_b_roll_segments(
        task_id=task_id,
        timeline=timeline,
        product_profile=product_profile,
        request=request,
    )

    # ── 12. Subtitles ─────────────────────────────────────────────────────────
    await _stage("rendering_subtitles", "📝 Generating subtitles...")
    from services.subtitle_service import SubtitleService
    ss = SubtitleService(config)
    subtitle_path = await ss.generate_srt(task_id, timeline, audio_assets)

    # ── 13. Overlay plan ──────────────────────────────────────────────────────
    from services.overlay_service import OverlayService
    overlay_plan = OverlayService(config).build_plan(timeline, a_roll_assets, b_roll_assets)

    # ── 14. Compose ───────────────────────────────────────────────────────────
    await _stage("compositing", "🎞 Compositing final video...")
    from core.video_stitcher import TimelineComposer
    composer = TimelineComposer(config)
    final_video_path = await composer.compose(
        task_id=task_id,
        timeline=timeline,
        a_roll_assets=a_roll_assets,
        b_roll_assets=b_roll_assets,
        subtitle_path=subtitle_path,
        bgm_path=None,
        overlay_plan=overlay_plan,
        file_store=file_store,
    )

    # ── 15. QA ────────────────────────────────────────────────────────────────
    await _stage("qa_review", "🔍 Quality checking final video...")
    from services.qa_service import QAService
    qa_report = await QAService(config).run(
        timeline=timeline,
        final_video_path=final_video_path,
        subtitle_path=subtitle_path,
        a_roll_assets=a_roll_assets,
        b_roll_assets=b_roll_assets,
        audio_assets=audio_assets,
    )
    final_video_score = VideoScoringService().score(timeline, qa_report)
    from core.publish_prep_service import PublishPrepService
    from core.asset_reuse_pool import AssetReusePool
    publish_package = PublishPrepService().build(
        request=request,
        product_profile=product_profile,
        presenter_profile=presenter_profile,
        production_plan=production_plan,
        timeline=timeline,
        final_video_path=final_video_path,
    )
    reuse_pool = AssetReusePool(config)
    asset_pool_entry = reuse_pool.save_entry(
        request=request,
        product_profile=product_profile,
        payload={
            "task_id": task_id,
            "hook_lines": [c.get("hook_line", "") for c in script_batch_report.get("candidates", []) if c.get("hook_line")],
            "selected_variant_id": script_batch_report.get("selected_variant_id", ""),
            "publish_package": publish_package.to_dict(),
            "reusable_assets": publish_package.reusable_assets,
            "video_score": final_video_score.to_dict(),
        },
    )
    asset_pool_summary = reuse_pool.summarize(request=request, product_profile=product_profile)
    from core.platform_publish_adapter import PlatformPublishAdapter
    from core.publish_queue import PublishQueue
    publish_adapter = PlatformPublishAdapter()
    publish_payload = publish_adapter.build_payload(
        platform=getattr(request, 'platform', 'douyin'),
        publish_package=publish_package.to_dict(),
        final_video_path=final_video_path,
        subtitle_path=subtitle_path,
        task_id=task_id,
    )
    publish_queue = PublishQueue(config)
    publish_queue_entry = publish_queue.enqueue(
        task_id=task_id,
        platform=getattr(request, 'platform', 'douyin'),
        payload=publish_payload.to_dict(),
        priority='high' if final_video_score.total_score >= 80 else 'normal',
    )

    # ── 16. Persist outputs ───────────────────────────────────────────────────
    video_dir.mkdir(parents=True, exist_ok=True)
    final_fname = Path(final_video_path).name
    output_video = video_dir / final_fname
    if Path(final_video_path) != output_video:
        shutil.copy2(final_video_path, output_video)

    task.result_filename = final_fname
    task.qa_report_json  = qa_report.to_dict() if hasattr(qa_report, "to_dict") else {}
    task.qa_report_json["video_score"] = final_video_score.to_dict()
    task.qa_report_json["publish_preparation"] = publish_package.to_dict()
    task.qa_report_json["asset_reuse_pool"] = {"entry": asset_pool_entry, "summary": asset_pool_summary}
    task.qa_report_json["platform_publish_payload"] = publish_payload.to_dict()
    task.qa_report_json["publish_queue"] = publish_queue_entry
    from core.review_state_machine import ReviewStateMachine
    task.qa_report_json["review_state"] = ReviewStateMachine().transition({}, new_status="draft", actor="system", note="auto-created after render")
    if subtitle_path and Path(subtitle_path).exists():
        sub_fname = Path(subtitle_path).name
        shutil.copy2(subtitle_path, video_dir / sub_fname)
        task.subtitle_filename = sub_fname

    task.status       = TaskStatus.completed
    task.completed_at = datetime.now(timezone.utc)
    task.progress_segment = task.progress_total = len(timeline.segments)
    await db.commit()

    # Optional Drive upload
    try:
        from services.google_drive import GoogleDriveService
        drive = GoogleDriveService(config)
        if drive.is_available():
            link = await drive.upload_video(final_video_path, f"ugc_{task_id}")
            task.result_drive_link = link
            await db.commit()
    except Exception as e:
        logger.warning(f"Drive upload skipped: {e}")

    # ── 17. Broadcast completion ──────────────────────────────────────────────
    await _stage("completed", "✅ UGC video ready!")
    await broadcast_progress(task_id, {
        "task_id": task_id, "event": "status",
        "status": "completed", "stage": "completed",
        "result_filename": final_fname,
        "qa_passed": getattr(qa_report, "passed", True),
    })
    logger.info(f"[{task_id}] ✅ Complete: {final_fname}")


# ════════════════════════════════════════════════════════════════════════════════
# LEGACY PIPELINE
# ════════════════════════════════════════════════════════════════════════════════

async def run_video_generation(task_id: str, config: dict, user_numeric_id: int):
    async with AsyncSessionLocal() as db:
        stmt = select(VideoTask).where(VideoTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            return
        task.status = TaskStatus.processing
        await db.commit()
        try:
            from core.orchestrator import Orchestrator
            orch = Orchestrator(config)
            upload_dir = Path(config.get("web", {}).get("upload_dir", "/app/data/uploads"))
            video_dir  = Path(config.get("web", {}).get("video_dir",  "/app/data/videos"))

            async def _progress(segment: int, total: int, message: str = ""):
                task.progress_segment = segment
                task.progress_total   = total
                await db.commit()
                await broadcast_progress(task_id, {
                    "task_id": task_id, "event": "progress",
                    "status": "processing",
                    "segment": segment, "total": total, "message": message,
                })

            image_path = str(upload_dir / task.image_filename) if task.image_filename else None
            result = await orch.generate_legacy(
                task_id=task_id,
                mode=task.mode,
                model=task.model,
                duration=task.duration,
                language=task.language,
                aspect_ratio=task.aspect_ratio,
                quality_tier=task.quality_tier or "economy",
                image_path=image_path,
                url=task.url,
                text_prompt=task.text_prompt,
                progress_callback=_progress,
            )
            video_dir.mkdir(parents=True, exist_ok=True)
            task.result_filename   = result.get("filename")
            task.result_drive_link = result.get("drive_link")
            task.status            = TaskStatus.completed
            task.completed_at      = datetime.now(timezone.utc)
            await db.commit()
            await broadcast_progress(task_id, {
                "task_id": task_id, "event": "status",
                "status": "completed",
                "result_filename": task.result_filename,
                "drive_link": task.result_drive_link,
            })
        except Exception as e:
            logger.exception(f"Legacy task {task_id} failed: {e}")
            task.status = TaskStatus.failed
            task.error_message = str(e)
            await db.commit()
            await broadcast_progress(task_id, {
                "task_id": task_id, "event": "error",
                "status": "failed", "error": str(e),
            })
