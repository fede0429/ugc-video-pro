"""
models/veo.py
=============
Google Veo 3.0 / 3.0 Pro / 3.1 Pro video generation adapter.

The key advantage of Veo for frame chaining:
    Veo uses the input image as the LITERAL FIRST FRAME of the video.
    This creates seamless visual continuity when frame chaining.

API Flow (Gemini API via generativelanguage.googleapis.com/v1beta):
    POST /v1beta/models/{model}:predictLongRunning
         → returns {name: "operations/OPERATION_ID"}
    GET  /v1beta/{operation_name}
         → poll until done: true
         → response.generateVideoResponse.generatedSamples[0].video.uri

Model names for Gemini API (generativelanguage.googleapis.com):
    - veo-3.0-generate-preview
    - veo-3.0-fast-generate-preview
    - veo-3.1-generate-preview
    - veo-3.1-fast-generate-preview

Reference: https://ai.google.dev/gemini-api/docs/video
"""

import asyncio
import base64
import time
from pathlib import Path
from typing import Optional

import aiohttp

from models.base import GenerationJob, VideoModelAdapter
from utils.logger import get_logger

logger = get_logger(__name__)

VEO_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

VEO_MODELS = {
    "veo_3": {
        "api_model": "veo-3.0-generate-preview",
        "max_seconds": 8,
        "supports_audio": True,
    },
    "veo_3_pro": {
        "api_model": "veo-3.0-generate-preview",
        "max_seconds": 8,
        "supports_audio": True,
        "quality": "high",
    },
    "veo_31_pro": {
        "api_model": "veo-3.1-generate-preview",
        "max_seconds": 8,
        "supports_audio": True,
        "quality": "high",
    },
}

VEO_ASPECT_RATIOS = {
    "9:16": "9:16",
    "16:9": "16:9",
    "1:1": "1:1",
    "4:3": "4:3",
    "3:4": "3:4",
}


class VeoAdapter(VideoModelAdapter):
    """Google Veo 3.x video generation adapter.
    
    Input image is used as the LITERAL FIRST FRAME — ideal for frame chaining.
    """

    def __init__(self, config: dict, model_variant: str = "veo_31_pro"):
        super().__init__(config)
        self._model_variant = model_variant
        self._model_config = VEO_MODELS[model_variant]
        self._api_key = config.get("models", {}).get("google", {}).get("api_key", "")
        if not self._api_key:
            logger.warning("Google API key not configured for Veo adapter")

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

    def _api_url(self, path: str) -> str:
        return f"{VEO_BASE_URL}/{path}?key={self._api_key}"

    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a Veo video generation job via long-running operation."""
        actual_duration = min(duration, self.max_duration)
        if duration > self.max_duration:
            logger.warning(
                f"Requested {duration}s > Veo max {self.max_duration}s; "
                f"clamping to {self.max_duration}s"
            )

        veo_aspect = VEO_ASPECT_RATIOS.get(aspect_ratio, "9:16")
        api_model = self._model_config["api_model"]

        generation_config: dict = {
            "durationSeconds": actual_duration,
            "aspectRatio": veo_aspect,
            "numberOfVideos": 1,
        }

        instance: dict = {"prompt": prompt}

        if reference_image and Path(reference_image).exists():
            try:
                with open(reference_image, "rb") as f:
                    img_bytes = f.read()

                img_b64 = base64.b64encode(img_bytes).decode()
                suffix = Path(reference_image).suffix.lower()
                mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

                instance["image"] = {
                    "bytesBase64Encoded": img_b64,
                    "mimeType": mime,
                }
                logger.debug(
                    f"Attached reference image to Veo: {reference_image} "
                    f"({len(img_bytes) / 1024:.0f} KB, {mime})"
                )
            except Exception as e:
                logger.warning(f"Could not attach reference image to Veo: {e}")

        url = self._api_url(f"models/{api_model}:predictLongRunning")
        body = {
            "instances": [instance],
            "parameters": generation_config,
        }

        logger.info(
            f"Submitting Veo job: model={api_model}, duration={actual_duration}s, "
            f"has_image={reference_image is not None}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp_text = await resp.text()
                if resp.status not in (200, 201, 202):
                    raise RuntimeError(f"Veo API error {resp.status}: {resp_text[:500]}")
                data = await resp.json()

        operation_name = data.get("name", "")
        if not operation_name:
            raise RuntimeError(f"No operation name in Veo response: {data}")

        logger.info(f"Veo operation submitted: {operation_name}")
        return operation_name

    async def poll_status(self, job_id: str) -> GenerationJob:
        """Poll Veo long-running operation status."""
        op_name = job_id.lstrip("/")
        url = self._api_url(op_name)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    return GenerationJob(
                        job_id=job_id, model_name=self.model_key, prompt="",
                        duration=0, reference_image=None, submitted_at=0,
                        status="failed", error="Operation not found (404)",
                    )
                resp.raise_for_status()
                data = await resp.json()

        is_done = data.get("done", False)
        error = data.get("error")

        if error:
            return GenerationJob(
                job_id=job_id, model_name=self.model_key, prompt="",
                duration=0, reference_image=None, submitted_at=0,
                status="failed", error=error.get("message", str(error)),
            )

        if not is_done:
            metadata = data.get("metadata", {})
            state = metadata.get("state", "PENDING")
            return GenerationJob(
                job_id=job_id, model_name=self.model_key, prompt="",
                duration=0, reference_image=None, submitted_at=0,
                status="processing" if state in ("RUNNING", "ACTIVE") else "pending",
            )

        # Extract video URI from completed operation
        # Gemini API uses: response.generateVideoResponse.generatedSamples[0].video.uri
        # Vertex AI uses: response.videos[0].gcsUri
        response = data.get("response", {})
        video_uri = None

        # Try Gemini API format first
        gen_response = response.get("generateVideoResponse", {})
        samples = gen_response.get("generatedSamples", [])
        if samples:
            video_uri = samples[0].get("video", {}).get("uri")

        # Fallback to Vertex AI format
        if not video_uri:
            videos = response.get("videos", response.get("generatedSamples", []))
            if videos:
                first_video = videos[0]
                video_uri = (
                    first_video.get("uri") or first_video.get("gcsUri")
                    or first_video.get("video", {}).get("uri")
                )

        if not video_uri and is_done:
            video_uri = response.get("uri") or response.get("videoUri")

        return GenerationJob(
            job_id=job_id, model_name=self.model_key, prompt="",
            duration=0, reference_image=None, submitted_at=0,
            status="succeeded" if is_done else "processing",
            video_url=video_uri,
        )

    async def download(self, job: GenerationJob) -> str:
        """Download Veo generated video from URI."""
        output_path = str(
            self.output_dir / f"veo_{self.model_key}_{int(time.time())}.mp4"
        )

        if not job.video_url:
            raise RuntimeError(f"No video URI for Veo job {job.job_id}")

        video_uri = job.video_url

        if video_uri.startswith("gs://"):
            parts = video_uri[5:].split("/", 1)
            bucket = parts[0]
            obj_path = parts[1] if len(parts) > 1 else ""
            import urllib.parse
            encoded_path = urllib.parse.quote(obj_path, safe="")
            video_uri = (
                f"https://storage.googleapis.com/storage/v1/b/{bucket}"
                f"/o/{encoded_path}?alt=media"
            )
            video_uri += f"&key={self._api_key}"

        # For Gemini API URIs, append the API key
        if "generativelanguage.googleapis.com" in video_uri:
            separator = "&" if "?" in video_uri else "?"
            video_uri += f"{separator}key={self._api_key}"

        logger.info(f"Downloading Veo video from: {video_uri[:80]}...")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                video_uri, timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f"Veo download error {resp.status}: {(await resp.text())[:300]}"
                    )
                with open(output_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        file_size = Path(output_path).stat().st_size
        logger.info(f"Downloaded Veo video: {output_path} ({file_size / 1024 / 1024:.1f} MB)")
        return output_path
