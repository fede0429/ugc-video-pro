"""
core/orchestrator.py
====================
Main pipeline controller for UGC Video Pro.

The orchestrator coordinates the entire video generation workflow:

    1. Analyze product image (Gemini Vision)
       → Extracts exact colors, materials, shape for prompt fidelity

    2. Extract URL content (if URL mode)
       → Gets product description, features, selling points

    3. Generate AI script (Gemini)
       → Segments the total duration into clips
       → Creates unique scene prompts with continuation hints

    4. Frame chain generation (FrameChainer)
       → Generates each clip sequentially
       → Extracts last frame → feeds to next clip
       → Ensures visual continuity across segments

    5. Stitch all clips (VideoStitcher + FFmpeg)
       → Crossfade or direct concat
       → Final MP4 output

    6. Upload to Google Drive (optional)
       → Returns shareable link

    7. Return VideoResult to Telegram handler

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


class VideoOrchestrator:
    """
    Orchestrates the full UGC video generation pipeline.
    
    Usage:
        orchestrator = VideoOrchestrator(config)
        result = await orchestrator.generate(request, progress_callback=..., status_callback=...)
    """

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.image_analyzer = ImageAnalyzer(config)
        self.url_extractor = URLExtractor(config)
        self.script_generator = ScriptGenerator(config)
        self.frame_chainer = FrameChainer(config)
        self.video_stitcher = VideoStitcher(config)

        drive_config = config.get("google_drive", {})
        if drive_config.get("credentials_path"):
            self.drive_uploader = GoogleDriveUploader(config)
        else:
            self.drive_uploader = None

    async def generate(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        """
        Run the complete video generation pipeline.
        
        Returns:
            VideoResult with path to final video and optional Drive link
        """
        start_time = time.time()

        logger.info(
            f"Starting pipeline: mode={request.mode}, model={request.model}, "
            f"duration={request.duration}s, user={request.user_id}"
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
