"""
models/kie_video.py
====================
KIE.AI-based unified video model adapter.

Routes ALL video generation through KIE.AI gateway:
    - Seedance 1.5 Pro (text-to-video, image-to-video) → /api/v1/jobs/createTask
    - Veo 3.1 (text-to-video, image-to-video) → /api/v1/veo/generate
    - Sora 2 (text-to-video, image-to-video) → /api/v1/jobs/createTask
    - Runway (text-to-video, image-to-video) → /api/v1/runway/generate
    - Kling 3.0 / 2.6 → /api/v1/jobs/createTask
    - Hailuo 2.3 / 02 → /api/v1/jobs/createTask

Different KIE.AI model families use different API endpoints and
parameter formats. This adapter handles the routing transparently.
"""

import base64
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from models.base import GenerationJob, VideoModelAdapter
from services.kie_gateway import KieGateway, KieProvider, TaskState
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Model registry — all KIE.AI video models
#
# Model names verified against KIE.AI docs (March 2026):
#   - Kling 3.0: "kling-3.0/video" (requires multi_shots, sound, mode)
#   - Kling 2.6: "kling-2.6/text-to-video" / "kling-2.6/image-to-video"
#   - Hailuo 2.3: "hailuo/2-3-image-to-video-standard" etc.
#   - Hailuo 02:  "hailuo/02-text-to-video-pro" etc.
#   - Seedance:   "bytedance/seedance-1.5-pro"
#   - Sora 2:     "sora-2-text-to-video" / "sora-2-image-to-video"
#   - Veo 3.1:    "veo3_fast" / "veo3_quality" (via /api/v1/veo/*)
#   - Runway:     "runway-duration-5-generate" (via /api/v1/runway/*)
# ──────────────────────────────────────────────────────────────

KIE_VIDEO_MODELS = {
    # ── Seedance (generic endpoint) ──────────────────────
    "seedance_15": {
        "kie_model_t2v": "bytedance/seedance-1.5-pro",
        "kie_model_i2v": "bytedance/seedance-1.5-pro",
        "provider": KieProvider.GENERIC,
        "input_style": "generic",
        "max_seconds": 10,
        "exact_reference": True,
        "supports_i2v": True,
        "default_resolution": "1080p",
    },
    "seedance_2": {
        "kie_model_t2v": "bytedance/seedance-2-text-to-video",
        "kie_model_i2v": "bytedance/seedance-2-text-to-video",
        "provider": KieProvider.GENERIC,
        "input_style": "generic",
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
        "input_style": "veo",
        "max_seconds": 8,
        "exact_reference": True,
        "supports_i2v": True,
        "quality_tier": "fast",
    },
    "veo_31_quality": {
        "kie_model_t2v": "veo3_quality",
        "kie_model_i2v": "veo3_quality",
        "provider": KieProvider.VEO,
        "input_style": "veo",
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
        "input_style": "sora",
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
        "input_style": "runway",
        "max_seconds": 5,
        "exact_reference": False,
        "supports_i2v": True,
        "default_resolution": "720p",
    },

    # ── Kling 3.0 (generic endpoint, special input format) ──
    # KIE model name: "kling-3.0/video"
    # Required fields: multi_shots, sound, mode
    # Reference images use "image_urls" (not "input_urls")
    "kling_30": {
        "kie_model_t2v": "kling-3.0/video",
        "kie_model_i2v": "kling-3.0/video",
        "provider": KieProvider.GENERIC,
        "input_style": "kling30",
        "max_seconds": 15,
        "exact_reference": True,
        "supports_i2v": True,
        "supports_audio": True,
    },

    # ── Kling 2.6 (generic endpoint) ─────────────────────
    # KIE model names: "kling-2.6/text-to-video" / "kling-2.6/image-to-video"
    "kling_26": {
        "kie_model_t2v": "kling-2.6/text-to-video",
        "kie_model_i2v": "kling-2.6/image-to-video",
        "provider": KieProvider.GENERIC,
        "input_style": "kling26",
        "max_seconds": 10,
        "exact_reference": False,
        "supports_i2v": True,
        "supports_audio": True,
    },

    # ── Hailuo 2.3 (generic endpoint) ────────────────────
    # No 2.3 t2v on KIE; use 02-text-to-video-standard for t2v
    "hailuo_23": {
        "kie_model_t2v": "hailuo/02-text-to-video-standard",
        "kie_model_i2v": "hailuo/2-3-image-to-video-standard",
        "provider": KieProvider.GENERIC,
        "input_style": "hailuo",
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },

    # ── Hailuo 2.3 Pro (generic endpoint) ────────────────
    "hailuo_23_pro": {
        "kie_model_t2v": "hailuo/02-text-to-video-pro",
        "kie_model_i2v": "hailuo/2-3-image-to-video-pro",
        "provider": KieProvider.GENERIC,
        "input_style": "hailuo",
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },

    # ── Hailuo 02 (generic endpoint) ─────────────────────
    "hailuo_02": {
        "kie_model_t2v": "hailuo/02-text-to-video-standard",
        "kie_model_i2v": "hailuo/02-image-to-video-standard",
        "provider": KieProvider.GENERIC,
        "input_style": "hailuo",
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },

    # ── Hailuo 02 Pro (generic endpoint) ─────────────────
    "hailuo_02_pro": {
        "kie_model_t2v": "hailuo/02-text-to-video-pro",
        "kie_model_i2v": "hailuo/02-image-to-video-pro",
        "provider": KieProvider.GENERIC,
        "input_style": "hailuo",
        "max_seconds": 6,
        "exact_reference": False,
        "supports_i2v": True,
    },
}

# Backward-compatible aliases
_ALIASES = {
    "hailuo": "hailuo_23",
}


class KieVideoAdapter(VideoModelAdapter):
    """
    Unified video generation adapter routing through KIE.AI.

    Replaces individual Sora/Veo/Seedance adapters with a single
    gateway that supports all models via provider-specific endpoints.
    """

    def __init__(self, config: dict, model_variant: str = "veo_31_fast"):
        super().__init__(config)

        # Resolve aliases
        resolved = _ALIASES.get(model_variant, model_variant)
        self._model_variant = resolved

        if resolved not in KIE_VIDEO_MODELS:
            raise ValueError(
                f"Unknown KIE video model: {model_variant}. "
                f"Available: {list(KIE_VIDEO_MODELS.keys())}"
            )

        self._model_config = KIE_VIDEO_MODELS[resolved]
        self._provider = self._model_config.get("provider", KieProvider.GENERIC)
        self._input_style = self._model_config.get("input_style", "generic")
        self._gateway = KieGateway(config)

        # Public base URL for serving media files (used by models that need HTTP URLs)
        web_cfg = config.get("web", {})
        public_host = web_cfg.get("public_host", "46.225.212.66")
        public_port = web_cfg.get("public_port", 8001)
        self._public_base_url = f"http://{public_host}:{public_port}/api/media"

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

    # ──────────────────────────────────────────────────────
    # Input builders — one per input_style
    # ──────────────────────────────────────────────────────

    # Models that REQUIRE actual HTTP URLs (reject base64 data URLs)
    _UPLOAD_REQUIRED_STYLES = {"kling30", "kling26", "hailuo"}

    # Local media hosting: images copied here are served at /api/media/
    _UPLOADS_DIR = Path("/app/data/uploads")

    def _resolve_image_base64(self, reference_image: str) -> Optional[str]:
        """Convert a local file path to a data URL, or pass through if URL."""
        if reference_image.startswith(("http://", "https://")):
            return reference_image
        if Path(reference_image).exists():
            try:
                with open(reference_image, "rb") as f:
                    img_bytes = f.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                suffix = Path(reference_image).suffix.lower()
                mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                return f"data:{mime};base64,{img_b64}"
            except Exception as e:
                logger.warning(f"Could not read reference image: {e}")
                return None
        return None

    def _host_image_locally(self, file_path: str) -> Optional[str]:
        """
        Make an image accessible via HTTP URL.

        If the file is already under /app/data/uploads/, construct the URL directly.
        Otherwise, copy it there first. The FastAPI app serves this dir at /api/media/.
        """
        src = Path(file_path)
        if not src.exists():
            logger.warning(f"Image file not found for hosting: {file_path}")
            return None

        try:
            # Check if already under uploads dir — no copy needed
            try:
                rel_path = src.resolve().relative_to(self._UPLOADS_DIR.resolve())
                public_url = f"{self._public_base_url}/{rel_path}"
                logger.info(f"Image already in uploads dir: {public_url}")
                return public_url
            except ValueError:
                pass  # Not under uploads dir, need to copy

            # Copy to uploads dir with unique name
            unique_name = f"{uuid.uuid4().hex[:12]}{src.suffix.lower()}"
            dest = self._UPLOADS_DIR / unique_name
            self._UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

            public_url = f"{self._public_base_url}/{unique_name}"
            logger.info(
                f"Hosted image locally: {src.name} -> {public_url}"
            )
            return public_url
        except Exception as e:
            logger.error(f"Failed to host image locally: {e}")
            return None

    async def _resolve_image(self, reference_image: str) -> Optional[str]:
        """
        Resolve a reference image to a URL suitable for the current model.

        For models that accept base64 data URLs (Veo, Seedance, Sora, Runway):
            -> returns data:image/... URL
        For models that REQUIRE HTTP URLs (Kling 3.0/2.6, Hailuo):
            -> copies to local uploads dir and returns public HTTP URL
        If input is already an HTTP URL:
            -> passes through as-is
        """
        # Already an HTTP URL — always pass through
        if reference_image.startswith(("http://", "https://")):
            return reference_image

        # Local file — check if model needs HTTP URL or accepts base64
        if not Path(reference_image).exists():
            logger.warning(f"Reference image not found: {reference_image}")
            return None

        if self._input_style in self._UPLOAD_REQUIRED_STYLES:
            # Host locally and return HTTP URL
            return self._host_image_locally(reference_image)
        else:
            # Base64 data URL is fine for this model
            return self._resolve_image_base64(reference_image)

    async def _build_input_generic(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Generic endpoint (Seedance, Kling legacy, etc.).
        Nested under 'input' in the request body.
        """
        input_params: dict = {
            "prompt": prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
        }

        resolution = self._model_config.get("default_resolution")
        if resolution:
            input_params["resolution"] = resolution

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["input_urls"] = [img_url]

        if self._model_config.get("supports_audio"):
            input_params["generate_audio"] = True

        return input_params

    async def _build_input_kling30(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Kling 3.0: model="kling-3.0/video"
        Required fields: multi_shots, sound, mode, duration (str "3"-"15")
        Reference images go in image_urls (not input_urls).
        Images MUST be HTTP URLs (base64 data URLs are rejected).
        """
        input_params: dict = {
            "prompt": prompt,
            "duration": str(min(duration, 15)),
            "aspect_ratio": aspect_ratio,
            "mode": "std",        # std = 720p, pro = 1080p
            "multi_shots": False,  # single-shot mode
            "sound": True,         # native audio generation
        }

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["image_urls"] = [img_url]

        return input_params

    async def _build_input_kling26(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Kling 2.6: model="kling-2.6/text-to-video" or "kling-2.6/image-to-video"
        Uses sound, duration, aspect_ratio.
        Reference images: image_url (singular string, not array).
        Images MUST be HTTP URLs (base64 data URLs are rejected).
        """
        input_params: dict = {
            "prompt": prompt,
            "duration": str(min(duration, 10)),
            "aspect_ratio": aspect_ratio,
            "sound": True,
        }

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["image_url"] = img_url

        return input_params

    async def _build_input_hailuo(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Hailuo 2.3 / 02: uses prompt, duration, image_url, resolution.
        Images MUST be HTTP URLs (base64 data URLs are rejected).
        """
        input_params: dict = {
            "prompt": prompt,
        }

        # Duration: "6" or "10"
        if duration <= 6:
            input_params["duration"] = "6"
        else:
            input_params["duration"] = "10"

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["image_url"] = img_url

        return input_params

    async def _build_input_sora(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Sora 2: model="sora-2-text-to-video" / "sora-2-image-to-video"
        Uses n_frames, aspect_ratio as "landscape"/"portrait".
        """
        input_params: dict = {
            "prompt": prompt,
            "n_frames": str(min(duration, 10)),
        }

        if aspect_ratio in ("16:9", "landscape"):
            input_params["aspect_ratio"] = "landscape"
        else:
            input_params["aspect_ratio"] = "portrait"

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["image_urls"] = [img_url]

        return input_params

    async def _build_input_veo(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Veo 3.1: flat body params (NOT nested under 'input')."""
        input_params: dict = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "enableTranslation": True,
        }

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["imageUrls"] = [img_url]
                input_params["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"
        else:
            input_params["generationType"] = "TEXT_2_VIDEO"

        return input_params

    async def _build_input_runway(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Runway: flat body params."""
        input_params: dict = {
            "prompt": prompt,
            "waterMark": "",
        }

        if aspect_ratio in ("16:9",):
            input_params["aspectRatio"] = "horizontal"
        else:
            input_params["aspectRatio"] = "vertical"

        input_params["duration"] = 5 if duration <= 5 else 10

        resolution = self._model_config.get("default_resolution", "720p")
        input_params["quality"] = resolution

        if reference_image:
            img_url = await self._resolve_image(reference_image)
            if img_url:
                input_params["imageUrl"] = img_url

        return input_params

    # ──────────────────────────────────────────────────────
    # Main API
    # ──────────────────────────────────────────────────────

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
        builder = {
            "veo": self._build_input_veo,
            "runway": self._build_input_runway,
            "sora": self._build_input_sora,
            "kling30": self._build_input_kling30,
            "kling26": self._build_input_kling26,
            "hailuo": self._build_input_hailuo,
            "generic": self._build_input_generic,
        }.get(self._input_style, self._build_input_generic)

        input_params = await builder(
            prompt=prompt,
            duration=actual_duration,
            reference_image=reference_image,
            aspect_ratio=aspect_ratio,
        )

        if is_continuation and self._input_style == "generic":
            input_params["fixed_lens"] = True

        logger.info(
            f"KIE video generate: variant={self._model_variant}, "
            f"provider={self._provider.value}, kie_model={kie_model}, "
            f"style={self._input_style}, duration={actual_duration}s, "
            f"has_ref={has_reference}"
        )

        task = await self._gateway.create_task(
            kie_model,
            input_params,
            provider=self._provider,
        )

        # Store provider info in task_id for later polling
        return f"{self._provider.value}:{task.task_id}"

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll KIE.AI task status."""
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
