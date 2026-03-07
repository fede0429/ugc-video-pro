"""
models/base.py
==============
Abstract base class for all video generation model adapters.

Every model adapter must implement:
    - generate(): submit a generation job, return job_id
    - poll_status(): check if job is done
    - download(): download the completed video

The base class provides:
    - calculate_segments(): split total duration into clips
    - Retry logic with exponential backoff
    - Standardized logging
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class GenerationJob:
    """Represents an in-flight generation job."""
    job_id: str
    model_name: str
    prompt: str
    duration: int
    reference_image: Optional[str]
    submitted_at: float
    status: str = "pending"     # pending | processing | succeeded | failed
    video_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of a completed generation job."""
    video_path: str
    job_id: str
    duration: int
    model_name: str
    elapsed_seconds: float


# ─────────────────────────────────────────────────────────────
# Model max duration registry
# ─────────────────────────────────────────────────────────────

MODEL_MAX_DURATIONS = {
    # Legacy direct API models
    "sora_2": 10,        # KIE.AI max 10s
    "sora_2_pro": 25,
    "seedance_2": 12,    # KIE.AI valid: 4,5,8,10,12 → max 12s
    "veo_3": 8,
    "veo_3_pro": 8,
    "veo_31_pro": 8,
    # KIE.AI models — values must match kie_video.py max_seconds
    "seedance_15": 12,       # valid: 4, 8, 12 → max 12s
    "veo_31_fast": 8,        # max 8s
    "veo_31_quality": 8,     # max 8s
    "runway": 5,             # KIE.AI: runway-duration-5-generate → max 5s
    "runway_1080p": 5,       # max 5s
    "kling_26": 10,          # max 10s
    "kling_30": 15,          # KIE.AI: 3-15s → max 15s
    "hailuo": 6,             # max 6s
}


def get_model_max_duration(model: str) -> int:
    """Get maximum clip duration for a model."""
    return MODEL_MAX_DURATIONS.get(model, 8)


def get_valid_duration_multiples(model: str, max_total: int = 120, count: int = 5) -> list[int]:
    """Generate a list of valid duration multiples for a model."""
    max_clip = get_model_max_duration(model)
    multiples = []
    n = 1
    while len(multiples) < count:
        val = max_clip * n
        if val > max_total:
            break
        multiples.append(val)
        n += 1
    return multiples


def nearest_valid_duration(model: str, value: int) -> int:
    """Find the nearest valid duration (multiple of model max clip)."""
    max_clip = get_model_max_duration(model)
    if value <= 0:
        return max_clip
    rounded = round(value / max_clip) * max_clip
    return max(rounded, max_clip)


# ─────────────────────────────────────────────────────────────
# Abstract base class
# ─────────────────────────────────────────────────────────────

class VideoModelAdapter(ABC):
    """Abstract base for all video generation model adapters."""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._poll_config = config.get("polling", {})

    @property
    @abstractmethod
    def model_key(self) -> str:
        """Internal model key (e.g. 'veo_31_fast')."""

    @property
    @abstractmethod
    def max_duration(self) -> int:
        """Maximum single clip duration in seconds."""

    @property
    def supports_exact_reference(self) -> bool:
        """Whether this model uses reference image as the literal first frame."""
        return False

    @property
    def supports_image_to_video(self) -> bool:
        """Whether this model accepts a reference image."""
        return True

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a video generation job. Returns job_id string."""

    @abstractmethod
    async def poll_status(self, job_id: str) -> GenerationJob:
        """Check the status of a generation job."""

    @abstractmethod
    async def download(self, job: GenerationJob) -> str:
        """Download a completed video to local disk."""

    def calculate_segments(self, target_duration: int) -> list[int]:
        """Calculate segment durations for a target total duration."""
        max_d = self.max_duration
        num_segments = -(-target_duration // max_d)  # ceiling division
        base = target_duration // num_segments
        remainder = target_duration % num_segments
        durations = [base + (1 if i < remainder else 0) for i in range(num_segments)]
        
        logger.debug(
            f"Segment calc: model={self.model_key}, "
            f"target={target_duration}s, max_clip={max_d}s, "
            f"segments={num_segments}, durations={durations}"
        )
        return durations

    async def poll_until_complete(
        self,
        job_id: str,
        poll_interval: Optional[float] = None,
        max_retries: Optional[int] = None,
        on_poll: Optional[callable] = None,
    ) -> GenerationJob:
        """Poll a job until it succeeds, fails, or times out."""
        if poll_interval is None:
            poll_interval = self._poll_config.get(
                f"{self.model_key.split('_')[0]}_interval", 45
            )
        if max_retries is None:
            max_retries = self._poll_config.get("max_retries", 30)

        backoff_factor = self._poll_config.get("backoff_factor", 1.5)

        for attempt in range(1, max_retries + 1):
            logger.debug(
                f"Polling {self.model_key} job {job_id}: "
                f"attempt {attempt}/{max_retries}"
            )

            if on_poll:
                await on_poll(attempt, max_retries)

            job = await self.poll_status(job_id)

            if job.status == "succeeded":
                logger.info(f"Job {job_id} succeeded after {attempt} polls")
                return job

            if job.status == "failed":
                error = job.error or "Unknown model error"
                logger.error(f"Job {job_id} failed: {error}")
                raise RuntimeError(f"Video generation failed: {error}")

            wait = min(
                poll_interval * (backoff_factor ** (attempt - 1)), 120
            )
            logger.debug(
                f"Job {job_id} status={job.status}, waiting {wait:.0f}s"
            )
            await asyncio.sleep(wait)

        raise TimeoutError(
            f"Job {job_id} timed out after {max_retries} polling attempts "
            f"({max_retries * poll_interval / 60:.1f} min)"
        )

    async def generate_and_download(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
        on_poll: Optional[callable] = None,
    ) -> GenerationResult:
        """Submit, poll, and download a video clip in one call."""
        start = time.time()

        logger.info(
            f"Submitting {self.model_key} job: duration={duration}s, "
            f"has_ref={reference_image is not None}, "
            f"continuation={is_continuation}"
        )

        job_id = await self.generate(
            prompt=prompt,
            duration=duration,
            reference_image=reference_image,
            is_continuation=is_continuation,
            aspect_ratio=aspect_ratio,
        )

        job = await self.poll_until_complete(job_id, on_poll=on_poll)
        video_path = await self.download(job)

        elapsed = time.time() - start
        logger.info(f"Job {job_id} complete: {video_path} ({elapsed:.1f}s)")

        return GenerationResult(
            video_path=video_path,
            job_id=job_id,
            duration=duration,
            model_name=self.model_key,
            elapsed_seconds=elapsed,
        )
