"""
models/seedance.py
==================
Seedance 2.0 video generation adapter.

API: ByteDance/Seedance API (REST)
    POST /v1/video_generation
    GET  /v1/video_generation/{task_id}
"""

import time
from pathlib import Path
from typing import Optional

import aiohttp

from models.base import GenerationJob, VideoModelAdapter
from utils.logger import get_logger

logger = get_logger(__name__)

SEEDANCE_MODELS = {
    "seedance_2": {
        "api_model": "seedance-1-0-lite-i2v-250428",
        "api_model_t2v": "seedance-1-0-lite-t2v-250428",
        "max_seconds": 10,
    },
}

SEEDANCE_RESOLUTIONS = {
    "9:16": "720x1280",
    "16:9": "1280x720",
    "1:1": "720x720",
}


class SeedanceAdapter(VideoModelAdapter):
    """Seedance 2.0 video generation adapter."""

    def __init__(self, config: dict, model_variant: str = "seedance_2"):
        super().__init__(config)
        self._model_variant = model_variant
        self._model_config = SEEDANCE_MODELS[model_variant]
        self._api_key = config.get("models", {}).get("seedance", {}).get("api_key", "")
        self._base_url = config.get("models", {}).get("seedance", {}).get(
            "base_url", "https://api.seedance.ai/v1"
        )
        if not self._api_key:
            logger.warning("Seedance API key not configured")

    @property
    def model_key(self) -> str:
        return self._model_variant

    @property
    def max_duration(self) -> int:
        return self._model_config["max_seconds"]

    @property
    def supports_exact_reference(self) -> bool:
        return True

    @property
    def supports_image_to_video(self) -> bool:
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a Seedance video generation job."""
        actual_duration = min(duration, self.max_duration)
        resolution = SEEDANCE_RESOLUTIONS.get(aspect_ratio, SEEDANCE_RESOLUTIONS["9:16"])

        if reference_image and Path(reference_image).exists():
            api_model = self._model_config["api_model"]
        else:
            api_model = self._model_config["api_model_t2v"]

        body: dict = {
            "model": api_model,
            "prompt": prompt,
            "duration": actual_duration,
            "resolution": resolution,
            "watermark": False,
        }

        if reference_image and Path(reference_image).exists():
            import base64
            with open(reference_image, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            suffix = Path(reference_image).suffix.lower()
            mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            body["image"] = f"data:{mime};base64,{img_b64}"

        if is_continuation:
            body["camera_fixed"] = True

        logger.info(
            f"Submitting Seedance job: model={api_model}, "
            f"duration={actual_duration}s, has_image={reference_image is not None}"
        )

        url = f"{self._base_url}/video_generation"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=body, headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp_text = await resp.text()
                if resp.status not in (200, 201, 202):
                    raise RuntimeError(f"Seedance API error {resp.status}: {resp_text[:500]}")
                data = await resp.json()

        task_id = (
            data.get("id") or data.get("task_id") or data.get("data", {}).get("id")
        )
        if not task_id:
            raise RuntimeError(f"No task_id in Seedance response: {data}")

        logger.info(f"Seedance task submitted: {task_id}")
        return task_id

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll Seedance task status."""
        url = f"{self._base_url}/video_generation/{job_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    return GenerationJob(
                        job_id=job_id, model_name=self.model_key, prompt="",
                        duration=0, reference_image=None, submitted_at=0,
                        status="failed", error="Task not found (404)",
                    )
                resp.raise_for_status()
                data = await resp.json()

        raw_status = (
            data.get("status") or data.get("state") or data.get("data", {}).get("status", "pending")
        )
        status_map = {
            "pending": "pending", "queued": "pending",
            "running": "processing", "processing": "processing", "in_progress": "processing",
            "succeeded": "succeeded", "completed": "succeeded", "done": "succeeded",
            "failed": "failed", "error": "failed",
        }
        status = status_map.get(raw_status.lower() if raw_status else "pending", "pending")

        video_url = None
        if status == "succeeded":
            video_url = (
                data.get("video_url") or data.get("url")
                or data.get("data", {}).get("video", {}).get("url")
                or data.get("data", {}).get("url")
                or data.get("output", {}).get("url")
            )

        error_msg = None
        if status == "failed":
            error_msg = (
                data.get("error") or data.get("message")
                or data.get("data", {}).get("error") or "Seedance generation failed"
            )

        return GenerationJob(
            job_id=job_id, model_name=self.model_key, prompt="",
            duration=0, reference_image=None, submitted_at=0,
            status=status, video_url=video_url,
            error=str(error_msg) if error_msg else None,
        )

    async def download(self, job: GenerationJob) -> str:
        """Download Seedance generated video."""
        output_path = str(
            self.output_dir / f"seedance_{job.job_id[:12]}_{int(time.time())}.mp4"
        )

        if not job.video_url:
            raise RuntimeError(f"No video URL for Seedance task {job.job_id}")

        logger.info(f"Downloading Seedance video from: {job.video_url[:80]}...")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                job.video_url, timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f"Seedance download error {resp.status}: {(await resp.text())[:300]}"
                    )
                with open(output_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Downloaded Seedance video: {output_path} ({file_size / 1024 / 1024:.1f} MB)")
        return output_path
