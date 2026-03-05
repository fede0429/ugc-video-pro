"""
models/kie_video.py
====================
KIE.AI-based unified video model adapter.

Routes ALL video generation through KIE.AI gateway:
    - Seedance 1.5 Pro (text-to-video, image-to-video) → /api/v1/jobs/createTask
    - Veo 3.1 (text-to-video, image-to-video) → /api/v1/veo/generate
    - Sora 2 (text-to-video, image-to-video) → /api/v1/jobs/createTask
    - Runway (text-to-video, image-to-video) → /api/v1/runway/generate

Different KIE.AI model families use different API endpoints and
parameter formats. This adapter handles the routing transparently.
"""

import base64
import time
from pathlib import Path
from typing import Optional

from models.base import GenerationJob, VideoModelAdapter
from services.kie_gateway import KieGateway, KieProvider, TaskState
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Model registry — all KIE.AI video models
# ──────────────────────────────────────────────────────────────

KIE_VIDEO_MODELS = {
    # ── Seedance (generic endpoint) ──────────────────────
    "seedance_15": {
        "kie_model_t2v": "bytedance/seedance-1.5-pro",
        "kie_model_i2v": "bytedance/seedance-1.5-pro",
        "provider": KieProvider.GENERIC,
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "default_resolution": "1080p",
    },
    "seedance_2": {
        "kie_model_t2v": "bytedance/seedance-2-text-to-video",
        "kie_model_i2v": "bytedance/seedance-2-text-to-video",
        "provider": KieProvider.GENERIC,
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "default_resolution": "1080p",
        "coming_soon": True,  # Not yet available on KIE.AI
    },

    # ── Veo 3.1 (dedicated /api/v1/veo/* endpoint) ──────
    "veo_31_fast": {
        "kie_model_t2v": "veo3_fast",
        "kie_model_i2v": "veo3_fast",
        "provider": KieProvider.VEO,
        "max_seconds": 8,
        "exact_reference": True,
        "supports_i2v": True,
        "quality_tier": "fast",
    },
    "veo_31_quality": {
        "kie_model_t2v": "veo3_quality",
        "kie_model_i2v": "veo3_quality",
        "provider": KieProvider.VEO,
        "max_seconds": 8,
        "exact_reference": True,
        "supports_i2v": True,
        "quality_tier": "quality",
    },

    # ── Sora 2 (generic endpoint) ────────────────────────
    "sora_2": {
        "kie_model_t2v": "sora-2-text-to-video",
        "kie_model_i2v": "sora-2-image-to-video",
        "provider": KieProvider.GENERIC,
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "stable",
    },

    # ── Runway (dedicated /api/v1/runway/* endpoint) ─────
    "runway": {
        "kie_model_t2v": "runway-duration-5-generate",
        "kie_model_i2v": "runway-duration-5-generate",
        "provider": KieProvider.RUNWAY,
        "max_seconds": 5,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "720p",
    },

    # ── Kling (generic endpoint) ─────────────────────────
    "kling_26": {
        "kie_model_t2v": "kling-2.6/text-to-video",
        "kie_model_i2v": "kling-2.6/text-to-video",
        "provider": KieProvider.GENERIC,
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "supports_audio": True,
    },
    "kling_30": {
        "kie_model_t2v": "kling-3.0/text-to-video",
        "kie_model_i2v": "kling-3.0/text-to-video",
        "provider": KieProvider.GENERIC,
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "supports_audio": True,
    },

    # ── Hailuo (generic endpoint) ────────────────────────
    "hailuo": {
        "kie_model_t2v": "minimax/hailuo-2.3",
        "kie_model_i2v": "minimax/hailuo-2.3",
        "provider": KieProvider.GENERIC,
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },
}


class KieVideoAdapter(VideoModelAdapter):
    """
    Unified video generation adapter routing through KIE.AI.

    Replaces individual Sora/Veo/Seedance adapters with a single
    gateway that supports all models via provider-specific endpoints.
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
        self._provider = self._model_config.get("provider", KieProvider.GENERIC)
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

    def _build_input_generic(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Build input params for GENERIC endpoint (Sora, Seedance, Kling, Hailuo).
        These go nested under 'input' in the request body.
        """
        input_params: dict = {
            "prompt": prompt,
        }

        # Duration
        if "kling" in self._model_variant or "seedance" in self._model_variant:
            input_params["duration"] = str(duration)
        elif "hailuo" in self._model_variant:
            input_params["duration"] = str(duration)
        elif "sora" in self._model_variant:
            # Sora uses n_frames: "10" or "15"
            input_params["n_frames"] = str(min(duration, 10))
            # Sora aspect_ratio is "landscape" or "portrait"
            if aspect_ratio in ("16:9", "landscape"):
                input_params["aspect_ratio"] = "landscape"
            else:
                input_params["aspect_ratio"] = "portrait"
        else:
            input_params["duration"] = duration

        # Aspect ratio (non-Sora models)
        if "sora" not in self._model_variant:
            input_params["aspect_ratio"] = aspect_ratio

        # Resolution
        resolution = self._model_config.get("default_resolution")
        if resolution and "sora" not in self._model_variant:
            input_params["resolution"] = resolution

        # Reference image (for image-to-video)
        if reference_image:
            if reference_image.startswith(("http://", "https://")):
                # URL-based reference
                if "sora" in self._model_variant:
                    input_params["image_urls"] = [reference_image]
                else:
                    input_params["input_urls"] = [reference_image]
            elif Path(reference_image).exists():
                try:
                    with open(reference_image, "rb") as f:
                        img_bytes = f.read()
                    img_b64 = base64.b64encode(img_bytes).decode()
                    suffix = Path(reference_image).suffix.lower()
                    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                    data_url = f"data:{mime};base64,{img_b64}"
                    if "sora" in self._model_variant:
                        input_params["image_urls"] = [data_url]
                    else:
                        input_params["input_urls"] = [data_url]
                except Exception as e:
                    logger.warning(f"Could not attach reference image: {e}")

        # Audio flag (Kling, Seedance)
        if self._model_config.get("supports_audio"):
            input_params["generate_audio"] = True

        return input_params

    def _build_input_veo(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Build input params for VEO endpoint.
        These go flat in the request body (NOT nested under 'input').
        """
        input_params: dict = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "enableTranslation": True,
        }

        # Reference image → imageUrls + generationType
        if reference_image:
            if reference_image.startswith(("http://", "https://")):
                input_params["imageUrls"] = [reference_image]
                input_params["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"
            elif Path(reference_image).exists():
                try:
                    with open(reference_image, "rb") as f:
                        img_bytes = f.read()
                    img_b64 = base64.b64encode(img_bytes).decode()
                    suffix = Path(reference_image).suffix.lower()
                    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                    input_params["imageUrls"] = [f"data:{mime};base64,{img_b64}"]
                    input_params["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"
                except Exception as e:
                    logger.warning(f"Could not attach Veo reference image: {e}")
        else:
            input_params["generationType"] = "TEXT_2_VIDEO"

        return input_params

    def _build_input_runway(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Build input params for RUNWAY endpoint.
        These go flat in the request body (NOT nested under 'input').
        """
        input_params: dict = {
            "prompt": prompt,
            "waterMark": "",  # No watermark
        }

        # Runway uses different aspect ratio format
        if aspect_ratio in ("16:9",):
            input_params["aspectRatio"] = "horizontal"
        else:
            input_params["aspectRatio"] = "vertical"

        # Duration: 5 or 10
        if duration <= 5:
            input_params["duration"] = 5
        else:
            input_params["duration"] = 10

        # Quality
        resolution = self._model_config.get("default_resolution", "720p")
        input_params["quality"] = resolution

        # Reference image → imageUrl (singular)
        if reference_image:
            if reference_image.startswith(("http://", "https://")):
                input_params["imageUrl"] = reference_image
            elif Path(reference_image).exists():
                try:
                    with open(reference_image, "rb") as f:
                        img_bytes = f.read()
                    img_b64 = base64.b64encode(img_bytes).decode()
                    suffix = Path(reference_image).suffix.lower()
                    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                    input_params["imageUrl"] = f"data:{mime};base64,{img_b64}"
                except Exception as e:
                    logger.warning(f"Could not attach Runway reference image: {e}")

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
        has_reference = reference_image and (
            reference_image.startswith(("http://", "https://"))
            or Path(reference_image).exists()
        )
        if has_reference:
            kie_model = self._model_config["kie_model_i2v"]
        else:
            kie_model = self._model_config["kie_model_t2v"]

        # Build provider-specific input params
        if self._provider == KieProvider.VEO:
            input_params = self._build_input_veo(
                prompt=prompt,
                duration=actual_duration,
                reference_image=reference_image,
                aspect_ratio=aspect_ratio,
            )
        elif self._provider == KieProvider.RUNWAY:
            input_params = self._build_input_runway(
                prompt=prompt,
                duration=actual_duration,
                reference_image=reference_image,
                aspect_ratio=aspect_ratio,
            )
        else:
            input_params = self._build_input_generic(
                prompt=prompt,
                duration=actual_duration,
                reference_image=reference_image,
                aspect_ratio=aspect_ratio,
            )

        if is_continuation and self._provider == KieProvider.GENERIC:
            input_params["fixed_lens"] = True

        logger.info(
            f"KIE video generate: variant={self._model_variant}, "
            f"provider={self._provider.value}, kie_model={kie_model}, "
            f"duration={actual_duration}s, has_ref={has_reference}"
        )

        task = await self._gateway.create_task(
            kie_model,
            input_params,
            provider=self._provider,
        )

        # Store provider info in task_id for later polling
        # Format: "provider:task_id" to route polling correctly
        return f"{self._provider.value}:{task.task_id}"

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll KIE.AI task status."""
        # Parse provider from composite job_id
        provider = KieProvider.GENERIC
        actual_task_id = job_id
        if ":" in job_id:
            parts = job_id.split(":", 1)
            try:
                provider = KieProvider(parts[0])
                actual_task_id = parts[1]
            except ValueError:
                actual_task_id = job_id

        try:
            task = await self._gateway.query_task(actual_task_id, provider=provider)
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
            / f"kie_{self._model_variant}_{job.job_id[-12:]}_{int(time.time())}.mp4"
        )

        return await self._gateway.download(job.video_url, output_path)
