"""
models/kie_video.py
====================
KIE.AI-based unified video model adapter.

Routes ALL video generation through KIE.AI gateway:
    - Seedance 1.5 Pro / 2.0 (text-to-video, image-to-video)
    - Veo 3.1 (text-to-video, image-to-video)
    - Sora 2 (text-to-video, image-to-video)
    - Runway (text-to-video, image-to-video)
    - Kling 2.6/3.0 (text-to-video, with audio)

All use the same createTask/recordInfo flow.
"""

import base64
import time
from pathlib import Path
from typing import Optional

from models.base import GenerationJob, VideoModelAdapter
from services.kie_gateway import KieGateway, TaskState
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Model registry — all KIE.AI video models
# ──────────────────────────────────────────────────────────────

KIE_VIDEO_MODELS = {
    # ── Seedance ──────────────────────────────────────────
    "seedance_15": {
        "kie_model_t2v": "bytedance/seedance-1.5-pro",
        "kie_model_i2v": "bytedance/seedance-1.5-pro",
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "default_resolution": "1080p",
    },
    "seedance_2": {
        "kie_model_t2v": "bytedance/seedance-2-text-to-video",
        "kie_model_i2v": "bytedance/seedance-2-text-to-video",
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "default_resolution": "1080p",
        "coming_soon": True,  # Not yet available on KIE.AI
    },

    # ── Veo 3.1 ──────────────────────────────────────────
    "veo_31_fast": {
        "kie_model_t2v": "google/veo-3.1/text-to-video",
        "kie_model_i2v": "google/veo-3.1/image-to-video",
        "max_seconds": 8,
        "exact_reference": True,
        "supports_i2v": True,
        "quality_tier": "fast",
    },
    "veo_31_quality": {
        "kie_model_t2v": "google/veo-3.1/text-to-video",
        "kie_model_i2v": "google/veo-3.1/image-to-video",
        "max_seconds": 8,
        "exact_reference": True,
        "supports_i2v": True,
        "quality_tier": "quality",
    },

    # ── Sora 2 ───────────────────────────────────────────
    "sora_2": {
        "kie_model_t2v": "openai/sora-2/text-to-video",
        "kie_model_i2v": "openai/sora-2/image-to-video",
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "stable",
    },

    # ── Runway ───────────────────────────────────────────
    "runway": {
        "kie_model_t2v": "runway/text-to-video",
        "kie_model_i2v": "runway/image-to-video",
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "720p",
    },
    "runway_1080p": {
        "kie_model_t2v": "runway/text-to-video",
        "kie_model_i2v": "runway/image-to-video",
        "max_seconds": 5,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "1080p",
    },

    # ── Kling ────────────────────────────────────────────
    "kling_26": {
        "kie_model_t2v": "kling-2.6/text-to-video",
        "kie_model_i2v": "kling-2.6/text-to-video",
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "supports_audio": True,
    },
    "kling_30": {
        "kie_model_t2v": "kling-3.0/text-to-video",
        "kie_model_i2v": "kling-3.0/text-to-video",
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "supports_audio": True,
    },

    # ── Hailuo (MiniMax) ─────────────────────────────────
    "hailuo": {
        "kie_model_t2v": "minimax/hailuo-2.3",
        "kie_model_i2v": "minimax/hailuo-2.3",
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },
}


class KieVideoAdapter(VideoModelAdapter):
    """
    Unified video generation adapter routing through KIE.AI.

    Replaces individual Sora/Veo/Seedance adapters with a single
    gateway that supports all models.
    """

    def __init__(self, config: dict, model_variant: str = "veo_31_fast"):
        super().__init__(config)
        self._model_variant = model_variant

        if model_variant not in KIE_VIDEO_MODELS:
            raise ValueError(
                f"Unknown KIE video model: {model_variant}. "
                f"Available: {list(KIE_VIDEO_MODELS.keys())}"
            )

        self._model_config = KIE_VIDEO_MODELS[model_variant]
        self._gateway = KieGateway(config)

        if self._model_config.get("coming_soon"):
            logger.warning(
                f"Model {model_variant} is marked 'coming soon' on KIE.AI. "
                f"Tasks may fail until the model is launched."
            )

    @property
    def model_key(self) -> str:
        return self._model_variant

    @property
    def max_duration(self) -> int:
        return self._model_config["max_seconds"]

    @property
    def supports_exact_reference(self) -> bool:
        return self._model_config.get("exact_reference", False)

    @property
    def supports_image_to_video(self) -> bool:
        return self._model_config.get("supports_i2v", True)

    def _build_input(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Build model-specific input parameters for KIE.AI createTask."""
        input_params: dict = {
            "prompt": prompt,
        }

        # Duration
        if "kling" in self._model_variant or "seedance" in self._model_variant:
            input_params["duration"] = str(duration)
        elif "hailuo" in self._model_variant:
            input_params["duration"] = str(duration)
        else:
            input_params["duration"] = duration

        # Aspect ratio
        input_params["aspect_ratio"] = aspect_ratio

        # Resolution
        resolution = self._model_config.get("default_resolution")
        if resolution:
            input_params["resolution"] = resolution

        # Quality tier (Veo)
        quality = self._model_config.get("quality_tier")
        if quality:
            input_params["quality"] = quality

        # Reference image (for image-to-video)
        if reference_image and Path(reference_image).exists():
            try:
                with open(reference_image, "rb") as f:
                    img_bytes = f.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                suffix = Path(reference_image).suffix.lower()
                mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                input_params["input_urls"] = [
                    f"data:{mime};base64,{img_b64}"
                ]
            except Exception as e:
                logger.warning(f"Could not attach reference image: {e}")

        # Audio flag (Kling)
        if self._model_config.get("supports_audio"):
            input_params["generate_audio"] = True

        return input_params

    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a video generation task via KIE.AI."""
        actual_duration = min(duration, self.max_duration)

        # Choose t2v or i2v model
        if reference_image and Path(reference_image).exists():
            kie_model = self._model_config["kie_model_i2v"]
        else:
            kie_model = self._model_config["kie_model_t2v"]

        input_params = self._build_input(
            prompt=prompt,
            duration=actual_duration,
            reference_image=reference_image,
            aspect_ratio=aspect_ratio,
        )

        if is_continuation:
            input_params["fixed_lens"] = True

        logger.info(
            f"KIE video generate: variant={self._model_variant}, "
            f"kie_model={kie_model}, duration={actual_duration}s, "
            f"has_ref={reference_image is not None}"
        )

        task = await self._gateway.create_task(kie_model, input_params)
        return task.task_id

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll KIE.AI task status."""
        try:
            task = await self._gateway.query_task(job_id)
        except Exception as e:
            return GenerationJob(
                job_id=job_id,
                model_name=self.model_key,
                prompt="",
                duration=0,
                reference_image=None,
                submitted_at=0,
                status="failed",
                error=str(e),
            )

        status_map = {
            TaskState.PENDING: "pending",
            TaskState.PROCESSING: "processing",
            TaskState.SUCCESS: "succeeded",
            TaskState.FAILED: "failed",
            TaskState.CANCELLED: "failed",
        }

        video_url = None
        if task.result_urls:
            video_url = task.result_urls[0]

        return GenerationJob(
            job_id=job_id,
            model_name=self.model_key,
            prompt="",
            duration=0,
            reference_image=None,
            submitted_at=0,
            status=status_map.get(task.state, "pending"),
            video_url=video_url,
            error=task.error,
        )

    async def download(self, job: GenerationJob) -> str:
        """Download video from KIE.AI result URL."""
        if not job.video_url:
            raise RuntimeError(
                f"No video URL for KIE task {job.job_id}"
            )

        output_path = str(
            self.output_dir
            / f"kie_{self._model_variant}_{job.job_id[:12]}_{int(time.time())}.mp4"
        )

        return await self._gateway.download(job.video_url, output_path)
