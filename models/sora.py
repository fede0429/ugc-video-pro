"""
models/sora.py
==============
OpenAI Sora 2 / Sora 2 Pro video generation adapter.

API endpoints:
    POST   https://api.openai.com/v1/videos/generations
    GET    https://api.openai.com/v1/videos/generations/{job_id}
    GET    https://api.openai.com/v1/videos/generations/{job_id}/content/video

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

SORA_BASE_URL = "https://api.openai.com/v1/videos/generations"

SORA_MODELS = {
    "sora_2": {
        "api_model": "sora",
        "max_seconds": 12,
        "default_resolution": "720p",
    },
    "sora_2_pro": {
        "api_model": "sora",
        "max_seconds": 25,
        "default_resolution": "1080p",
    },
}

SORA_RESOLUTIONS = {
    "9:16": "480x854",
    "16:9": "854x480",
    "1:1": "480x480",
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
        """Submit a Sora video generation job."""
        actual_duration = min(duration, self.max_duration)
        if duration > self.max_duration:
            logger.warning(
                f"Requested duration {duration}s > Sora max {self.max_duration}s; "
                f"clamping to {self.max_duration}s"
            )

        resolution = SORA_RESOLUTIONS.get(aspect_ratio, SORA_RESOLUTIONS["9:16"])

        body: dict = {
            "model": self._model_config["api_model"],
            "prompt": prompt,
            "n": 1,
            "size": resolution,
            "duration": actual_duration,
            "style": "vivid",
        }

        if reference_image and Path(reference_image).exists():
            try:
                with open(reference_image, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
                suffix = Path(reference_image).suffix.lower()
                mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
                body["input_image"] = f"data:{mime};base64,{img_data}"
                logger.debug(f"Attached reference image: {reference_image} ({mime})")
            except Exception as e:
                logger.warning(f"Could not attach reference image: {e}")

        logger.info(f"Submitting Sora job: model={body['model']}, duration={actual_duration}s")

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

        job_id = (
            data.get("id")
            or (data.get("data", [{}])[0] or {}).get("id")
            or data.get("generation_id")
        )
        if not job_id:
            raise RuntimeError(f"No job_id in Sora response: {data}")

        logger.info(f"Sora job submitted: {job_id}")
        return job_id

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll Sora job status."""
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

        raw_status = data.get("status", "pending")
        status_map = {
            "queued": "pending", "in_progress": "processing", "processing": "processing",
            "succeeded": "succeeded", "completed": "succeeded",
            "failed": "failed", "cancelled": "failed",
        }
        status = status_map.get(raw_status, "pending")

        video_url = None
        if status == "succeeded":
            generations = data.get("data", data.get("generations", []))
            if generations:
                video_url = generations[0].get("url") or generations[0].get("video_url")
            if not video_url:
                video_url = data.get("url") or data.get("video_url")

        return GenerationJob(
            job_id=job_id, model_name=self.model_key,
            prompt=data.get("prompt", ""), duration=data.get("duration", 0),
            reference_image=None, submitted_at=0, status=status,
            video_url=video_url,
            error=data.get("error", {}).get("message") if status == "failed" else None,
        )

    async def download(self, job: GenerationJob) -> str:
        """Download Sora generated video to local disk."""
        output_path = str(
            self.output_dir / f"sora_{job.job_id[:12]}_{int(time.time())}.mp4"
        )

        if job.video_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    job.video_url,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    resp.raise_for_status()
                    with open(output_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
        else:
            url = f"{SORA_BASE_URL}/{job.job_id}/content/video"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            f"Sora download error {resp.status}: {await resp.text()[:300]}"
                        )
                    with open(output_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Downloaded Sora video: {output_path} ({file_size / 1024 / 1024:.1f} MB)")
        return output_path
