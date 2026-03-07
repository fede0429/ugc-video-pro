"""
core/frame_chainer.py
=====================
BRollSequenceBuilder — generates B-roll product demo clips for the UGC timeline.

PDF Blueprint: frame_chainer is no longer a "last-frame continuation engine".
It is now a B-roll sequence builder that:
  1. Iterates B-roll segments from the TimelineScript
  2. Selects the best source image from the product image pool
       (primary / gallery / usage → based on shot_type / product_focus)
  3. Calls the video model router to generate each clip
  4. Returns list[RenderedAsset]

Legacy API (chain_segments, FrameChainer.chain_segments) is preserved
for backward compatibility with orchestrator.generate_legacy().
"""
from __future__ import annotations
import asyncio, os, time
from pathlib import Path
from typing import Callable, Optional

from core.timeline_types import (
    ExtendedUGCVideoRequest,
    ProductProfile,
    RenderedAsset,
    TimelineScript,
    UGCVideoRequest,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# VideoModelRouter — bridges BRollSequenceBuilder to the model layer
# ════════════════════════════════════════════════════════════════════════════════

class VideoModelRouter:
    """
    Selects the appropriate video model for each B-roll clip
    and dispatches the generation call.

    Wraps the existing KieGateway / model adapters behind a uniform interface.
    """

    def __init__(self, config: dict):
        self.config = config
        self._budget_tiers = {
            "economy": ["seedance_15", "runway"],
            "premium": ["veo_31_fast", "seedance_15"],
            "china":   ["kling_30", "hailuo", "seedance_15"],
        }

    def select_b_roll_model(self, payload: dict) -> "VideoModelRouter":
        """Return self (acts as model proxy) after recording chosen model."""
        quality_tier = payload.get("metadata", {}).get("quality_tier", "economy")
        preferred = self._budget_tiers.get(quality_tier, ["seedance_15"])
        # If caller specified a model, honour it
        explicit = payload.get("model")
        self._active_model = explicit if explicit and explicit != "auto" else preferred[0]
        return self

    @property
    def name(self) -> str:
        return getattr(self, "_active_model", "seedance_15")

    async def generate_b_roll(
        self,
        prompt: str,
        source_image: Optional[str],
        duration_seconds: float,
        shot_type: str,
        output_path: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Generate a single B-roll clip. Returns output_path."""
        try:
            from services.kie_gateway import KieGateway
            gateway = KieGateway(self.config)

            model = getattr(self, "_active_model", "seedance_15")
            duration_int = max(4, min(int(duration_seconds), 15))

            logger.info(f"B-roll gen: model={model} dur={duration_int}s shot={shot_type}")

            result = await gateway.generate_video(
                model=model,
                prompt=prompt,
                image_path=source_image,
                duration=duration_int,
                aspect_ratio=(metadata or {}).get("aspect_ratio", "9:16"),
                output_path=output_path,
            )
            return result.get("video_path", output_path)

        except Exception as e:
            logger.error(f"B-roll generation failed: {e}")
            raise


# ════════════════════════════════════════════════════════════════════════════════
# BRollSequenceBuilder — PDF blueprint implementation
# ════════════════════════════════════════════════════════════════════════════════

class BRollSequenceBuilder:
    """
    Generates all B-roll clips for a TimelineScript.

    Exact implementation of the PDF blueprint.
    Uses VideoModelRouter for model selection and dispatch.
    """

    def __init__(self, video_model_router=None, file_store=None, _logger=None, config: dict = None):
        self.video_model_router = video_model_router
        self.file_store = file_store
        self.logger = _logger or logger
        self.config = config or {}
        # Build router from config if not injected
        if self.video_model_router is None and self.config:
            self.video_model_router = VideoModelRouter(self.config)

    async def render_b_roll_segments(
        self,
        task_id: str,
        timeline: TimelineScript,
        product_profile: ProductProfile,
        request,   # UGCVideoRequest or ExtendedUGCVideoRequest
    ) -> list[RenderedAsset]:
        """
        Generate all B-roll clips for the timeline.
        Returns list[RenderedAsset] with paths to rendered video clips.
        """
        outputs: list[RenderedAsset] = []
        source_pool = self._build_source_pool(request)

        b_roll_segs = [s for s in timeline.segments if s.track_type == "b_roll"]
        b_roll_segs.sort(key=lambda s: s.segment_index)

        for segment in b_roll_segs:
            source_image = self._choose_best_source(
                segment=segment,
                source_pool=source_pool,
                product_profile=product_profile,
            )

            output_path = self.file_store.segment_video_path(
                task_id=task_id,
                segment_id=segment.segment_id,
                track_type="b_roll",
            )

            # Build the generation prompt from visual_prompt or b_roll_prompt
            visual_prompt = (
                segment.visual_prompt
                or segment.b_roll_prompt
                or self._fallback_prompt(segment, product_profile)
            )

            generation_payload = {
                "segment_id": segment.segment_id,
                "duration_seconds": float(segment.duration_seconds),
                "visual_prompt": visual_prompt,
                "shot_type": segment.shot_type or "product_demo",
                "product_focus": segment.product_focus if hasattr(segment, "product_focus") else "",
                "source_image": source_image,
                "consistency_anchors": product_profile.consistency_anchors,
                "aspect_ratio": getattr(request, "aspect_ratio", "9:16"),
                "model": getattr(request, "model", "auto"),
                "metadata": {
                    "platform": getattr(request, "platform", "douyin"),
                    "category": product_profile.category or product_profile.product_type,
                    "selling_points": product_profile.selling_points,
                    "quality_tier": getattr(request, "quality_tier", "economy"),
                    "aspect_ratio": getattr(request, "aspect_ratio", "9:16"),
                },
            }

            model = self.video_model_router.select_b_roll_model(generation_payload)

            try:
                await model.generate_b_roll(
                    prompt=visual_prompt,
                    source_image=source_image,
                    duration_seconds=float(segment.duration_seconds),
                    shot_type=segment.shot_type or "product_demo",
                    output_path=output_path,
                    metadata=generation_payload["metadata"],
                )
                outputs.append(RenderedAsset(
                    segment_id=segment.segment_id,
                    video_path=output_path,
                    duration_seconds=float(segment.duration_seconds),
                    track_type="b_roll",
                ))
                self.logger.info(
                    "b_roll segment rendered",
                    extra={
                        "task_id": task_id,
                        "segment_id": segment.segment_id,
                        "source_image": source_image,
                        "output_path": output_path,
                    },
                )
            except Exception as e:
                self.logger.error(f"[task={task_id}] B-roll failed for {segment.segment_id}: {e}")
                raise

        return outputs

    # ── Source pool ───────────────────────────────────────────────────────────

    def _build_source_pool(self, request) -> list[dict]:
        """Build the pool of available product images, labelled by kind."""
        pool: list[dict] = []

        # Try ExtendedUGCVideoRequest fields first
        primary = getattr(request, "product_primary_image", None)
        gallery = getattr(request, "product_gallery_images", []) or []
        usage   = getattr(request, "product_usage_images",  []) or []

        # Fall back to flat product_image_paths
        if not primary:
            paths = getattr(request, "product_image_paths", []) or []
            if paths:
                primary = paths[0]
                gallery = paths[1:]

        if primary:
            pool.append({"path": primary, "kind": "primary"})
        for path in gallery:
            if path:
                pool.append({"path": path, "kind": "gallery"})
        for path in usage:
            if path:
                pool.append({"path": path, "kind": "usage"})

        return pool

    def _choose_best_source(
        self,
        segment,
        source_pool: list[dict],
        product_profile: ProductProfile,
    ) -> Optional[str]:
        """
        Select the best source image for a B-roll segment based on shot_type.
        Exact PDF blueprint logic.
        """
        if not source_pool:
            return None

        shot_type    = (getattr(segment, "shot_type", "") or "").lower()
        product_focus= (getattr(segment, "product_focus", "") or "").lower()

        usage_candidates   = [i["path"] for i in source_pool if i["kind"] == "usage"]
        gallery_candidates = [i["path"] for i in source_pool if i["kind"] == "gallery"]
        primary_candidates = [i["path"] for i in source_pool if i["kind"] == "primary"]

        # Application / demo shots → prefer usage images
        if any(k in shot_type for k in ("apply", "demo", "use", "over_sink", "mirror")) \
                or "use" in product_focus:
            if usage_candidates:
                return usage_candidates[0]

        # Detail / texture shots → prefer gallery close-ups
        if any(k in shot_type for k in ("detail", "texture", "macro", "unbox")):
            if gallery_candidates:
                return gallery_candidates[0]

        # Default priority: primary → gallery → usage
        if primary_candidates:
            return primary_candidates[0]
        if gallery_candidates:
            return gallery_candidates[0]
        if usage_candidates:
            return usage_candidates[0]

        raise ValueError(f"No product source image available for b_roll segment {segment.segment_id}")

    def _fallback_prompt(self, segment, product_profile: ProductProfile) -> str:
        """Generate a fallback b_roll prompt when none is set on the segment."""
        brand = product_profile.brand or ""
        desc = product_profile.description or f"a {product_profile.product_type} product"
        shot = getattr(segment, "shot_type", "product_demo") or "product_demo"
        overlay = getattr(segment, "overlay_text", "") or ""
        return (
            f"Close-up product shot: {brand} {desc}. "
            f"Shot type: {shot}. "
            f"Clean studio lighting, 9:16 vertical format. "
            f"{'Text callout: ' + overlay if overlay else ''}"
        ).strip()


# ════════════════════════════════════════════════════════════════════════════════
# FrameChainer — legacy class kept for backward compat
# New code should use BRollSequenceBuilder directly.
# ════════════════════════════════════════════════════════════════════════════════

class FrameChainer:
    """
    Legacy frame-chaining engine.

    render_b_roll_segments() delegates to BRollSequenceBuilder.
    chain_segments() is preserved unchanged for orchestrator.generate_legacy().
    """

    def __init__(self, config: dict):
        self.config = config
        self._router = VideoModelRouter(config)
        self._builder: Optional[BRollSequenceBuilder] = None   # lazy init

        from utils.ffmpeg_tools import FFmpegTools
        self.ffmpeg = FFmpegTools(config)

        fc_config = config.get("frame_chaining", {})
        self.extract_offset       = fc_config.get("extract_offset", 0.1)
        self.frame_quality        = fc_config.get("frame_quality", 95)
        self.add_continuation_prefix = fc_config.get("add_continuation_prefix", True)
        self.continuation_prefix  = fc_config.get(
            "continuation_prefix",
            "Seamlessly continuing from the previous frame: "
        )
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_builder(self, file_store) -> BRollSequenceBuilder:
        return BRollSequenceBuilder(
            video_model_router=self._router,
            file_store=file_store,
            config=self.config,
        )

    # ── NEW delegating API ────────────────────────────────────────────────────

    async def render_b_roll_segments(
        self,
        task_id: str,
        timeline: TimelineScript,
        product_profile: ProductProfile,
        request,
        file_store,
    ) -> list[RenderedAsset]:
        """Delegate to BRollSequenceBuilder."""
        builder = self._get_builder(file_store)
        return await builder.render_b_roll_segments(
            task_id=task_id,
            timeline=timeline,
            product_profile=product_profile,
            request=request,
        )

    # ── LEGACY chain_segments ─────────────────────────────────────────────────

    async def chain_segments(
        self,
        script,             # VideoScript
        model_adapter,      # VideoModelAdapter
        progress_callback: Optional[Callable] = None,
    ) -> list[str]:
        """
        Legacy sequential frame-chain generation.
        Preserved verbatim from the original implementation.
        """
        from core.script_generator import VideoScene, VideoScript

        video_paths: list[str] = []
        reference_image: Optional[str] = None
        total = len(script.scenes)

        for i, scene in enumerate(script.scenes):
            prompt = scene.scene_prompt
            if self.add_continuation_prefix and reference_image:
                prompt = f"{self.continuation_prefix}{prompt}"
            if scene.continuation_hint and reference_image:
                prompt = f"{prompt}. {scene.continuation_hint}"

            out = str(self.output_dir / f"scene_{i:03d}_{int(time.time()*1000)}.mp4")
            logger.info(f"Chain seg {i+1}/{total}: {prompt[:80]}")

            try:
                result = await model_adapter.generate(
                    prompt=prompt,
                    duration=scene.duration,
                    reference_image=reference_image,
                    output_path=out,
                )
                video_path = result.video_path if hasattr(result, "video_path") else result
                video_paths.append(video_path)

                # Extract last frame for next segment
                frame_path = str(self.output_dir / f"frame_{i:03d}.jpg")
                try:
                    await self.ffmpeg.extract_frame(
                        video_path=video_path,
                        output_path=frame_path,
                        timestamp=-self.extract_offset,
                        quality=self.frame_quality,
                    )
                    reference_image = frame_path
                except Exception as e:
                    logger.warning(f"Frame extraction failed for seg {i}: {e}")
                    reference_image = None

                if progress_callback:
                    await progress_callback(i + 1, total, f"Generated clip {i+1}/{total}")
            except Exception as e:
                logger.error(f"Chain seg {i} failed: {e}")
                raise

        return video_paths
