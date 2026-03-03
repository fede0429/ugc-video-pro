"""
core/frame_chainer.py
=====================
THE MOST CRITICAL FILE — Frame chaining engine for seamless long video generation.

Key insight:
    AI models are limited to short clips (8-25 seconds).
    To make a 30-120 second UGC video, we chain multiple clips together.
    The key to SEAMLESS chaining: extract the LAST FRAME of clip N,
    and feed it as the STARTING IMAGE for clip N+1.

Model reference image behavior:
    Veo 3.x      → LITERAL FIRST FRAME — exact pixel continuity
    Seedance 2.0 → Strong reference lock — very close to first frame
    Sora 2/Pro   → Style reference — visual guidance, may drift

Continuation prompt strategy:
    - Exact reference (Veo/Seedance): focus on MOTION ONLY
    - Style reference (Sora): include full scene context
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Callable, Optional

from core.script_generator import VideoScene, VideoScript
from models.base import VideoModelAdapter, GenerationResult
from utils.ffmpeg_tools import FFmpegTools
from utils.logger import get_logger

logger = get_logger(__name__)


class FrameChainer:
    """
    Frame chaining engine for seamless multi-segment video generation.
    
    Generates all video segments sequentially, using the last frame of
    each clip as the starting image for the next clip.
    """

    def __init__(self, config: dict):
        self.config = config
        self.ffmpeg = FFmpegTools(config)
        fc_config = config.get("frame_chaining", {})
        self.extract_offset = fc_config.get("extract_offset", 0.1)
        self.frame_quality = fc_config.get("frame_quality", 95)
        self.add_continuation_prefix = fc_config.get("add_continuation_prefix", True)
        self.continuation_prefix = fc_config.get(
            "continuation_prefix",
            "Seamlessly continuing from the previous frame: "
        )
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def chain_segments(
        self,
        script: VideoScript,
        model_adapter: VideoModelAdapter,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
        progress_callback: Optional[Callable] = None,
        poll_callback: Optional[Callable] = None,
    ) -> list[str]:
        """
        Generate all video segments with frame chaining for visual continuity.
        
        Returns:
            List of local file paths to generated video clips (in order)
        """
        scenes = script.scenes
        total = len(scenes)
        video_paths: list[str] = []
        
        current_reference = reference_image
        
        logger.info(
            f"Starting frame chain: {total} segments, "
            f"model={model_adapter.model_key}, "
            f"exact_ref={model_adapter.supports_exact_reference}"
        )

        for i, scene in enumerate(scenes):
            logger.info(f"Generating segment {i + 1}/{total}: {scene.camera_movement}")

            prompt = self._build_segment_prompt(
                scene=scene,
                segment_index=i,
                total_segments=total,
                model_adapter=model_adapter,
                prev_scene=scenes[i - 1] if i > 0 else None,
            )

            eta = self._estimate_eta(i, total, model_adapter)

            if progress_callback:
                await progress_callback(
                    segment=i + 1,
                    total=total,
                    model=model_adapter.model_key.upper().replace("_", " "),
                    prompt=scene.scene_prompt,
                    eta=eta,
                )

            async def on_poll(attempt: int, max_retries: int, seg_idx=i):
                if poll_callback:
                    await poll_callback(attempt, max_retries)

            try:
                result: GenerationResult = await model_adapter.generate_and_download(
                    prompt=prompt,
                    duration=scene.duration_seconds,
                    reference_image=current_reference,
                    is_continuation=(i > 0),
                    aspect_ratio=aspect_ratio,
                    on_poll=on_poll,
                )
            except Exception as e:
                logger.error(f"Segment {i + 1} generation failed: {e}")
                raise RuntimeError(
                    f"Failed to generate segment {i + 1}/{total}: {e}"
                ) from e

            video_paths.append(result.video_path)
            logger.info(
                f"Segment {i + 1}/{total} complete: {result.video_path} "
                f"({result.elapsed_seconds:.0f}s)"
            )

            if i < total - 1:
                try:
                    frame_path = await self.extract_last_frame(
                        video_path=result.video_path,
                        segment_index=i,
                    )
                    current_reference = frame_path
                    logger.info(f"Extracted last frame from segment {i + 1}: {frame_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to extract last frame from segment {i + 1}: {e}. "
                        f"Falling back to original reference image."
                    )
                    current_reference = reference_image

        logger.info(f"Frame chain complete: {len(video_paths)} clips generated")
        return video_paths

    async def extract_last_frame(
        self,
        video_path: str,
        segment_index: int,
    ) -> str:
        """Extract the last frame of a video clip using ffmpeg."""
        output_path = str(
            self.output_dir / f"chain_frame_{segment_index}_{int(time.time())}.jpg"
        )

        offset = -abs(self.extract_offset)
        quality = str(self.frame_quality)

        cmd = [
            "ffmpeg", "-y",
            "-sseof", str(offset),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            "-vf", "scale=iw:ih",
            output_path,
        ]

        success, stdout, stderr = await self.ffmpeg.run_command(cmd, timeout=30)

        if not success or not Path(output_path).exists():
            logger.warning(
                f"Primary frame extraction failed for {video_path}, trying alternative"
            )
            cmd_alt = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", "select=eq(n\\,0)",
                "-vframes", "1",
                "-sseof", "-1",
                "-q:v", "2",
                output_path,
            ]
            success, stdout, stderr = await self.ffmpeg.run_command(cmd_alt, timeout=30)

        if not success or not Path(output_path).exists():
            raise RuntimeError(
                f"ffmpeg failed to extract last frame from {video_path}: {stderr[:300]}"
            )

        file_size = Path(output_path).stat().st_size
        logger.debug(
            f"Extracted frame {segment_index}: {output_path} "
            f"({file_size / 1024:.0f} KB)"
        )
        return output_path

    def _build_segment_prompt(
        self,
        scene: VideoScene,
        segment_index: int,
        total_segments: int,
        model_adapter: VideoModelAdapter,
        prev_scene: Optional[VideoScene],
    ) -> str:
        """Build the complete video generation prompt for a segment."""
        base_prompt = scene.scene_prompt

        if segment_index == 0:
            logger.debug(f"Segment 0: using full scene prompt")
            return self._append_audio_hint(base_prompt, scene.audio_description)

        if model_adapter.supports_exact_reference:
            continuation_parts = []

            if self.add_continuation_prefix:
                continuation_parts.append(self.continuation_prefix)

            if prev_scene and prev_scene.continuation_hint:
                continuation_parts.append(
                    f"Starting from: {prev_scene.continuation_hint}. "
                )

            continuation_parts.append(base_prompt)
            prompt = "".join(continuation_parts)
        else:
            context_parts = []

            if prev_scene and prev_scene.continuation_hint:
                context_parts.append(
                    f"[Continuing scene: {prev_scene.continuation_hint}] "
                )

            context_parts.append(base_prompt)
            prompt = "".join(context_parts)

        return self._append_audio_hint(prompt, scene.audio_description)

    def _append_audio_hint(self, prompt: str, audio_description: str) -> str:
        """Append audio description to video prompt if provided."""
        if audio_description and audio_description.strip():
            return f"{prompt.rstrip('.')}. Audio: {audio_description}"
        return prompt

    def _estimate_eta(
        self,
        current_segment: int,
        total_segments: int,
        model_adapter: VideoModelAdapter,
    ) -> str:
        """Estimate remaining generation time for progress messages."""
        avg_times = {
            "veo_3": 120, "veo_3_pro": 150, "veo_31_pro": 150,
            "sora_2": 90, "sora_2_pro": 120, "seedance_2": 60,
        }
        avg = avg_times.get(model_adapter.model_key, 90)
        remaining_segments = total_segments - current_segment
        total_secs = avg * remaining_segments

        if total_secs < 60:
            return f"{total_secs}s"
        elif total_secs < 3600:
            return f"{total_secs // 60}m {total_secs % 60}s"
        else:
            return f"{total_secs / 3600:.1f}h"

    async def cleanup_frames(self, frame_paths: list[str]) -> None:
        """Remove temporary frame images after use."""
        for path in frame_paths:
            try:
                if Path(path).exists():
                    os.unlink(path)
                    logger.debug(f"Cleaned up frame: {path}")
            except Exception as e:
                logger.warning(f"Could not delete frame {path}: {e}")
