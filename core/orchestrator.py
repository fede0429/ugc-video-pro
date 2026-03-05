"""
core/orchestrator.py
====================
Main pipeline controller for UGC Video Pro.

v3.0 — Director Agent Edition
    The orchestrator now delegates decision-making to the DirectorAgent
    (GPT 5.2 via KIE.AI Chat API) which acts as a "film director":
    - Analyzes product → chooses model → plans segments → budgets costs
    - Then delegates execution back to the deterministic pipeline

    Legacy mode (director disabled) still works as before.

Pipeline stages:
    1. Director plans production (model, segments, budget)  [NEW]
    2. Analyze product image (Gemini Vision)
    3. Extract URL content (if URL mode)
    4. Generate AI script (via ScriptGenerator)
    5. Frame chain generation (FrameChainer) — THE MOST CRITICAL STEP
    6. Stitch all clips (VideoStitcher + FFmpeg)
    7. Multi-language TTS generation (parallel)              [NEW]
    8. Upload to Google Drive (optional)
    9. Return VideoResult

This class is stateless — each call to generate() is independent.
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.frame_chainer import FrameChainer
from core.script_generator import ScriptGenerator
from core.video_stitcher import VideoStitcher
from models import get_model_adapter
from services.google_drive import GoogleDriveUploader
from services.image_analyzer import ImageAnalyzer
from services.url_extractor import URLExtractor
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VideoRequest:
    """Input parameters for a video generation job."""
    user_id: int
    chat_id: int
    mode: str
    model: str
    duration: int
    language: str
    text_prompt: str = ""
    image_path: Optional[str] = None
    url: Optional[str] = None
    url_content: Optional[str] = None
    num_segments: int = 0
    aspect_ratio: str = "9:16"
    quality_tier: str = "economy"   # NEW: economy | premium | china
    num_images: int = 1             # NEW: number of uploaded images


@dataclass
class VideoResult:
    """Result of a completed video generation pipeline."""
    video_path: str
    drive_link: Optional[str]
    duration: int
    num_segments: int
    model: str
    elapsed_seconds: float
    segment_paths: list[str] = field(default_factory=list)
    script_json: str = ""
    product_analysis: dict = field(default_factory=dict)
    # NEW: Director Agent metadata
    director_decisions: list[str] = field(default_factory=list)
    production_plan_json: str = ""
    estimated_cost_usd: float = 0.0
    tts_paths: dict = field(default_factory=dict)


class VideoOrchestrator:
    """
    Orchestrates the full UGC video generation pipeline.

    v3.0: Now powered by DirectorAgent for intelligent decision-making.
    Falls back to legacy hardcoded logic if Director is unavailable.

    Usage:
        orchestrator = VideoOrchestrator(config)
        result = await orchestrator.generate(request, progress_callback=..., status_callback=...)
    """

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Core pipeline modules (used by both Director and legacy modes)
        self.image_analyzer = ImageAnalyzer(config)
        self.url_extractor = URLExtractor(config)
        self.script_generator = ScriptGenerator(config)
        self.frame_chainer = FrameChainer(config)
        self.video_stitcher = VideoStitcher(config)

        # Google Drive uploader (optional)
        drive_config = config.get("google_drive", {})
        if drive_config.get("credentials_path"):
            self.drive_uploader = GoogleDriveUploader(config)
        else:
            self.drive_uploader = None

        # Director Agent (new in v3.0)
        self._director = None
        self._director_enabled = self._check_director_enabled(config)
        if self._director_enabled:
            try:
                from core.director_agent import DirectorAgent
                self._director = DirectorAgent(config)
                logger.info("Director Agent initialized (GPT 5.2 via KIE.AI)")
            except Exception as e:
                logger.warning(f"Director Agent init failed: {e} — using legacy mode")
                self._director_enabled = False

    def _check_director_enabled(self, config: dict) -> bool:
        """Check if Director Agent should be enabled."""
        # Requires KIE.AI API key (for Chat API)
        kie_key = config.get("kie", {}).get("api_key", "")
        if not kie_key:
            return False
        # Check explicit config flag
        director_config = config.get("director", {})
        return director_config.get("enabled", True)  # Default: ON if KIE key exists

    async def generate(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        """
        Run the complete video generation pipeline.

        If Director Agent is available, it plans the production first.
        Otherwise, falls back to legacy hardcoded pipeline.

        Returns:
            VideoResult with path to final video and optional Drive link
        """
        if self._director_enabled and self._director:
            return await self._generate_with_director(
                request, progress_callback, status_callback
            )
        else:
            return await self._generate_legacy(
                request, progress_callback, status_callback
            )

    # ══════════════════════════════════════════════════════════
    # Director-Powered Pipeline (v3.0)
    # ══════════════════════════════════════════════════════════

    async def _generate_with_director(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        """
        Director Agent-powered pipeline.

        Phase 1: Director plans (model selection, segments, budget)
        Phase 2: Execute plan using existing modules
        """
        start_time = time.time()

        logger.info(
            f"[Director Mode] Starting pipeline: mode={request.mode}, "
            f"duration={request.duration}s, tier={request.quality_tier}, "
            f"lang={request.language}, user={request.user_id}"
        )

        async def update_status(key: str, **kwargs):
            if status_callback:
                await status_callback(key, **kwargs)

        # ── Phase 1: Director Planning ──────────────────────
        await update_status("director_planning")

        # Pre-analyze image for Director's context
        product_analysis = {}
        if request.image_path and Path(request.image_path).exists():
            await update_status("analyzing_image")
            try:
                product_analysis = await self.image_analyzer.analyze(
                    request.image_path
                )
                logger.info(f"Image analyzed: {product_analysis.get('type', 'unknown')}")
            except Exception as e:
                logger.warning(f"Image analysis failed: {e}")

        if request.text_prompt:
            product_analysis["user_description"] = request.text_prompt

        # Pre-extract URL content for Director's context
        url_content = request.url_content
        if request.url and not url_content:
            await update_status("extracting_url")
            try:
                url_content = await self.url_extractor.extract(request.url)
            except Exception as e:
                logger.warning(f"URL extraction failed: {e}")

        # Ask Director to plan
        try:
            plan = await self._director.create_production_plan(
                product_analysis=product_analysis,
                duration=request.duration,
                language=request.language,
                quality_tier=request.quality_tier,
                url_content=url_content,
                user_model_override=request.model if request.model != "auto" else None,
                num_images=request.num_images,
            )
            logger.info(
                f"[Director] Plan: model={plan.video_model}, "
                f"segments={plan.num_segments}, "
                f"cost=${plan.estimated_cost_usd:.2f}"
            )
        except Exception as e:
            logger.warning(f"Director planning failed: {e} — falling back to legacy")
            return await self._generate_legacy(
                request, progress_callback, status_callback
            )

        # ── Phase 2: Execute Plan ───────────────────────────
        effective_model = plan.video_model
        model_adapter = get_model_adapter(effective_model, self.config)

        logger.info(
            f"[Director] Segment plan: {plan.num_segments} clips, "
            f"durations={plan.segment_durations}, "
            f"exact_ref={model_adapter.supports_exact_reference}"
        )

        # Generate script
        await update_status("generating_script", segments=plan.num_segments)
        try:
            script = await self.script_generator.generate_script(
                product_analysis=product_analysis,
                segment_durations=plan.segment_durations,
                model_key=effective_model,
                language=request.language,
                url_content=url_content,
                aspect_ratio=request.aspect_ratio,
            )
        except Exception as e:
            raise RuntimeError(f"Script generation failed: {e}") from e

        logger.info(f"Script ready: {script.num_segments} scenes")

        # Frame chain generation
        async def poll_cb(attempt: int, max_retries: int):
            if status_callback:
                await status_callback(
                    "polling",
                    model=effective_model.upper().replace("_", " "),
                    attempt=attempt,
                    max_retries=max_retries,
                )

        try:
            segment_paths = await self.frame_chainer.chain_segments(
                script=script,
                model_adapter=model_adapter,
                reference_image=request.image_path,
                aspect_ratio=request.aspect_ratio,
                progress_callback=progress_callback,
                poll_callback=poll_cb,
            )
        except Exception as e:
            raise RuntimeError(f"Video generation failed: {e}") from e

        logger.info(f"Frame chain complete: {len(segment_paths)} clips")

        # Stitch clips
        await update_status("stitching", count=len(segment_paths))
        try:
            output_filename = (
                f"UGC_{request.mode}_{effective_model}_{request.duration}s_"
                f"{int(time.time())}.mp4"
            )
            output_path = str(self.output_dir / output_filename)
            final_path = await self.video_stitcher.stitch(
                video_paths=segment_paths,
                output_path=output_path,
            )
        except Exception as e:
            logger.error(f"Stitching failed: {e}")
            if segment_paths:
                logger.warning("Returning first clip due to stitching failure")
                final_path = segment_paths[0]
            else:
                raise RuntimeError(f"Video stitching failed: {e}") from e

        # TTS generation (multi-language, parallel)
        tts_paths = {}
        if plan.tts_languages:
            await update_status("generating_tts")
            tts_paths = await self._director._generate_multilang_tts(
                script=script,
                languages=plan.tts_languages,
                config=self.config,
            )

        # Upload to Google Drive
        drive_link = None
        if self.drive_uploader:
            await update_status("uploading_drive")
            try:
                drive_link = await self.drive_uploader.upload(
                    file_path=final_path,
                    folder_name=self.config.get(
                        "google_drive", {}
                    ).get("folder_name", "UGC_Videos"),
                )
            except Exception as e:
                logger.warning(f"Drive upload failed: {e}")
                await update_status("error_drive_upload")

        # Cleanup individual clips
        if len(segment_paths) > 1:
            for path in segment_paths:
                if path != final_path:
                    try:
                        if Path(path).exists():
                            os.unlink(path)
                    except Exception:
                        pass

        elapsed = time.time() - start_time
        logger.info(
            f"[Director] Pipeline complete: {final_path} "
            f"({elapsed:.0f}s total, {len(segment_paths)} clips, "
            f"model={effective_model})"
        )

        return VideoResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=request.duration,
            num_segments=plan.num_segments,
            model=effective_model,
            elapsed_seconds=elapsed,
            segment_paths=segment_paths,
            script_json=script.raw_json,
            product_analysis=product_analysis,
            director_decisions=self._director._decisions,
            production_plan_json=plan.raw_json,
            estimated_cost_usd=plan.estimated_cost_usd,
            tts_paths=tts_paths,
        )

    # ══════════════════════════════════════════════════════════
    # Legacy Pipeline (v2.x fallback)
    # ══════════════════════════════════════════════════════════

    async def _generate_legacy(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        """
        Original hardcoded pipeline (fallback when Director is unavailable).
        Preserved for backward compatibility.
        """
        start_time = time.time()

        logger.info(
            f"[Legacy Mode] Starting pipeline: mode={request.mode}, "
            f"model={request.model}, duration={request.duration}s, "
            f"user={request.user_id}"
        )

        async def update_status(key: str, **kwargs):
            if status_callback:
                await status_callback(key, **kwargs)

        # Step 1: Get the model adapter
        model_adapter = get_model_adapter(request.model, self.config)
        segment_durations = model_adapter.calculate_segments(request.duration)
        num_segments = len(segment_durations)

        logger.info(
            f"Segment plan: {num_segments} clips, "
            f"durations={segment_durations}, "
            f"exact_ref={model_adapter.supports_exact_reference}"
        )

        # Step 2: Analyze product image
        product_analysis = {}
        if request.image_path and Path(request.image_path).exists():
            await update_status("analyzing_image")
            try:
                product_analysis = await self.image_analyzer.analyze(request.image_path)
                logger.info(f"Image analyzed: {product_analysis.get('type', 'unknown')} product")
            except Exception as e:
                logger.warning(f"Image analysis failed: {e} — continuing without analysis")

        if request.text_prompt:
            product_analysis["user_description"] = request.text_prompt

        # Step 3: Extract URL content
        url_content = request.url_content
        if request.url and not url_content:
            await update_status("extracting_url")
            try:
                url_content = await self.url_extractor.extract(request.url)
                logger.info(f"URL extracted: {len(url_content or '')} chars")
            except Exception as e:
                logger.warning(f"URL extraction failed: {e} — continuing without URL content")
                url_content = None

        # Step 4: Generate script
        await update_status("generating_script", segments=num_segments)
        try:
            script = await self.script_generator.generate_script(
                product_analysis=product_analysis,
                segment_durations=segment_durations,
                model_key=request.model,
                language=request.language,
                url_content=url_content,
                aspect_ratio=request.aspect_ratio,
            )
        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            raise RuntimeError(f"Script generation failed: {e}") from e

        logger.info(f"Script ready: {script.num_segments} scenes")

        # Step 5: Frame chain generation
        async def poll_cb(attempt: int, max_retries: int):
            if status_callback:
                await status_callback(
                    "polling",
                    model=request.model.upper().replace("_", " "),
                    attempt=attempt,
                    max_retries=max_retries,
                )

        try:
            segment_paths = await self.frame_chainer.chain_segments(
                script=script,
                model_adapter=model_adapter,
                reference_image=request.image_path,
                aspect_ratio=request.aspect_ratio,
                progress_callback=progress_callback,
                poll_callback=poll_cb,
            )
        except Exception as e:
            logger.error(f"Frame chaining failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}") from e

        logger.info(f"Frame chain complete: {len(segment_paths)} clips")

        # Step 6: Stitch all clips
        await update_status("stitching", count=len(segment_paths))
        try:
            output_filename = (
                f"UGC_{request.mode}_{request.model}_{request.duration}s_"
                f"{int(time.time())}.mp4"
            )
            output_path = str(self.output_dir / output_filename)

            final_path = await self.video_stitcher.stitch(
                video_paths=segment_paths,
                output_path=output_path,
            )
        except Exception as e:
            logger.error(f"Stitching failed: {e}")
            if segment_paths:
                logger.warning("Returning first clip due to stitching failure")
                final_path = segment_paths[0]
            else:
                raise RuntimeError(f"Video stitching failed: {e}") from e

        # Step 7: Upload to Google Drive
        drive_link = None
        if self.drive_uploader:
            await update_status("uploading_drive")
            try:
                drive_link = await self.drive_uploader.upload(
                    file_path=final_path,
                    folder_name=self.config.get("google_drive", {}).get("folder_name", "UGC_Videos"),
                )
                logger.info(f"Uploaded to Google Drive: {drive_link}")
            except Exception as e:
                logger.warning(f"Google Drive upload failed: {e} — video will be sent directly")
                await update_status("error_drive_upload")

        # Cleanup individual clips
        if len(segment_paths) > 1:
            for path in segment_paths:
                if path != final_path:
                    try:
                        if Path(path).exists():
                            os.unlink(path)
                    except Exception:
                        pass

        elapsed = time.time() - start_time
        logger.info(
            f"Pipeline complete: {final_path} "
            f"({elapsed:.0f}s total, {len(segment_paths)} clips)"
        )

        return VideoResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=request.duration,
            num_segments=num_segments,
            model=request.model,
            elapsed_seconds=elapsed,
            segment_paths=segment_paths,
            script_json=script.raw_json,
            product_analysis=product_analysis,
        )
