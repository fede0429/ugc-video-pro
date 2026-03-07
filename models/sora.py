"""
models/sora.py
==============
OpenAI Sora 2 / Sora 2 Pro video generation adapter.

API endpoints (Videos API — preview):
    POST   https://api.openai.com/v1/videos
    GET    https://api.openai.com/v1/videos/{video_id}
    GET    https://api.openai.com/v1/videos/{video_id}/content

Reference: https://developers.openai.com/api/docs/guides/video-generation/

Note on frame chaining:
    Sora uses the input image as a STYLE/COMPOSITION REFERENCE,
    not as the literal first frame. This means frame chaining will work,
    but with slight visual drift between segments. For tighter continuity,
    use Veo models instead.
"""

import asyncio
import base64
import os
import time
from pathlib import Path
from typing import Optional

import aiohttp

from models.base import GenerationJob, VideoModelAdapter
from utils.logger import get_logger

logger = get_logger(__name__)

SORA_BASE_URL = "https://api.openai.com/v1/videos"

SORA_MODELS = {
    "sora_2": {
        "api_model": "sora-2",
        "max_seconds": 12,
        "default_resolution": "720p",
        "default_size": "1280x720",
    },
    "sora_2_pro": {
        "api_model": "sora-2-pro",
        "max_seconds": 22,
        "default_resolution": "1080p",
        "default_size": "1920x1080",
    },
}

# Sora uses "size" param: WIDTHxHEIGHT
SORA_SIZES = {
    "9:16": "720x1280",
    "16:9": "1280x720",
    "1:1": "720x720",
}


class SoraAdapter(VideoModelAdapter):
    """OpenAI Sora 2 / Sora 2 Pro adapter."""

    def __init__(self, config: dict, model_variant: str = "sora_2"):
        super().__init__(config)
        self._model_variant = model_variant
        self._model_config = SORA_MODELS[model_variant]
        self._api_key = config.get("models", {}).get("openai", {}).get("api_key", "")
        if not self._api_key:
            logger.warning("OpenAI API key not configured for Sora adapter")

    @property
    def model_key(self) -> str:
        return self._model_variant

    @property
    def max_duration(self) -> int:
        return self._model_config["max_seconds"]

    @property
    def supports_exact_reference(self) -> bool:
        return False

    @property
    def supports_image_to_video(self) -> bool:
        return True

    def _headers(self, content_type: str = "application/json") -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a Sora video generation job.

        The Videos API uses:
          - POST /v1/videos
          - "model", "prompt", "seconds", "size" as JSON fields
          - "input_reference" as multipart file for image-to-video
        """
        actual_duration = min(duration, self.max_duration)
        if duration > self.max_duration:
            logger.warning(
                f"Requested duration {duration}s > Sora max {self.max_duration}s; "
                f"clamping to {self.max_duration}s"
            )

        size = SORA_SIZES.get(aspect_ratio, SORA_SIZES["9:16"])

        # If we have a reference image, use multipart/form-data
        if reference_image and Path(reference_image).exists():
            return await self._generate_with_image(
                prompt, actual_duration, size, reference_image
            )

        # Text-to-video: simple JSON POST
        body: dict = {
            "model": self._model_config["api_model"],
            "prompt": prompt,
            "size": size,
            "seconds": actual_duration,
        }

        logger.info(
            f"Submitting Sora job: model={body['model']}, "
            f"seconds={actual_duration}s, size={size}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SORA_BASE_URL,
                json=body,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp_text = await resp.text()
                if resp.status not in (200, 201, 202):
                    raise RuntimeError(f"Sora API error {resp.status}: {resp_text[:500]}")
                data = await resp.json()

        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"No job id in Sora response: {data}")

        logger.info(f"Sora job submitted: {job_id}")
        return job_id

    async def _generate_with_image(
        self, prompt: str, seconds: int, size: str, image_path: str
    ) -> str:
        """Submit image-to-video job using multipart/form-data."""
        suffix = Path(image_path).suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        data = aiohttp.FormData()
        data.add_field("model", self._model_config["api_model"])
        data.add_field("prompt", prompt)
        data.add_field("size", size)
        data.add_field("seconds", str(seconds))
        data.add_field(
            "input_reference",
            open(image_path, "rb"),
            filename=Path(image_path).name,
            content_type=mime,
        )

        logger.info(
            f"Submitting Sora image-to-video job: model={self._model_config['api_model']}, "
            f"seconds={seconds}s, image={image_path}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SORA_BASE_URL,
                data=data,
                headers=self._headers(content_type=""),  # let aiohttp set multipart header
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp_text = await resp.text()
                if resp.status not in (200, 201, 202):
                    raise RuntimeError(f"Sora API error {resp.status}: {resp_text[:500]}")
                result = await resp.json()

        job_id = result.get("id")
        if not job_id:
            raise RuntimeError(f"No job id in Sora image-to-video response: {result}")

        logger.info(f"Sora image-to-video job submitted: {job_id}")
        return job_id

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll Sora job status via GET /v1/videos/{video_id}."""
        url = f"{SORA_BASE_URL}/{job_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    return GenerationJob(
                        job_id=job_id, model_name=self.model_key, prompt="",
                        duration=0, reference_image=None, submitted_at=0,
                        status="failed", error="Job not found (404)",
                    )
                resp.raise_for_status()
                data = await resp.json()

        raw_status = data.get("status", "queued")
        status_map = {
            "queued": "pending",
            "in_progress": "processing",
            "processing": "processing",
            "completed": "succeeded",
            "succeeded": "succeeded",
            "failed": "failed",
            "cancelled": "failed",
        }
        status = status_map.get(raw_status, "pending")

        return GenerationJob(
            job_id=job_id, model_name=self.model_key,
            prompt=data.get("prompt", ""), duration=data.get("seconds", 0),
            reference_image=None, submitted_at=0, status=status,
            video_url=None,  # download is separate endpoint
            error=data.get("error", {}).get("message") if status == "failed" else None,
        )

    async def download(self, job: GenerationJob) -> str:
        """Download Sora generated video via GET /v1/videos/{video_id}/content."""
        output_path = str(
            self.output_dir / f"sora_{job.job_id[:12]}_{int(time.time())}.mp4"
        )

        url = f"{SORA_BASE_URL}/{job.job_id}/content"
        logger.info(f"Downloading Sora video from: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f"Sora download error {resp.status}: {(await resp.text())[:300]}"
                    )
                with open(output_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Downloaded Sora video: {output_path} ({file_size / 1024 / 1024:.1f} MB)")
        return output_path
