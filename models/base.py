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


# ───────────────────────────────────────────────────────────────
# Data structures
# ───────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────
# Model max duration registry
# ───────────────────────────────────────────────────────────────

MODEL_MAX_DURATIONS = {
    "sora_2": 12,
    "sora_2_pro": 25,
    "seedance_2": 10,
    "veo_3": 8,
    "veo_3_pro": 8,
    "veo_31_pro": 8,
}


def get_model_max_duration(model: str) -> int:
    """Get maximum clip duration for a model."""
    return MODEL_MAX_DURATIONS.get(model, 8)


# ───────────────────────────────────────────────────────────────
# Abstract base class
# ───────────────────────────────────────────────────────────────

class VideoModelAdapter(ABC):
    """Abstract base for all video generation model adapters.
    
    Subclasses implement the three abstract methods:
        generate() → job_id string
        poll_status() → GenerationJob with updated status
        download() → local file path string
    
    The base class provides segment calculation and polling loops.
    """

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._poll_config = config.get("polling", {})

    # ── Properties to override ────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def model_key(self) -> str:
        """Internal model key (e.g. 'veo_31_pro')."""

    @property
    @abstractmethod
    def max_duration(self) -> int:
        """Maximum single clip duration in seconds."""

    @property
    def supports_exact_reference(self) -> bool:
        """Whether this model uses reference image as the literal first frame.
        
        Veo models: True (literal first frame — ideal for frame chaining)
        Sora models: False (style reference — may drift)
        Seedance: True (strong reference locking)
        """
        return False

    @property
    def supports_image_to_video(self) -> bool:
        """Whether this model accepts a reference image."""
        return True

    # ── Abstract methods ────────────────────────────────────────────────────────────

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a video generation job.
        
        Args:
            prompt: Video generation prompt
            duration: Desired clip duration in seconds
            reference_image: Path to local image file (for img2video)
            is_continuation: True if this is a frame-chained follow-on clip
            aspect_ratio: "9:16" (portrait) or "16:9" (landscape)
        
        Returns:
            job_id string for polling
        """

    @abstractmethod
    async def poll_status(self, job_id: str) -> GenerationJob:
        """Check the status of a generation job.
        
        Returns:
            GenerationJob with updated status field.
            status values: "pending" | "processing" | "succeeded" | "failed"
        """

    @abstractmethod
    async def download(self, job: GenerationJob) -> str:
        """Download a completed video to local disk.
        
        Args:
            job: GenerationJob with status == "succeeded"
        
        Returns:
            Absolute path to downloaded video file.
        """

    # ── Segment calculation ───────────────────────────────────────────────────────────

    def calculate_segments(self, target_duration: int) -> list[int]:
        """Calculate segment durations for a target total duration.
        
        Uses ceiling division to split the total duration evenly across
        the minimum number of clips needed.
        
        Args:
            target_duration: Total desired video duration in seconds
        
        Returns:
            List of integer durations (in seconds) for each clip.
            Sum of list == target_duration.
        
        Example:
            Veo (max 8s), target 30s → [8, 8, 8, 6] (4 clips)
            Sora 2 (max 12s), target 25s → [13, 12] ... wait, 13 > 12
            Actually → [9, 8, 8] (3 clips of 9+8+8=25)
        """
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

    # ── Poll until complete ───────────────────────────────────────────────────────────

    async def poll_until_complete(
        self,
        job_id: str,
        poll_interval: Optional[float] = None,
        max_retries: Optional[int] = None,
        on_poll: Optional[callable] = None,
    ) -> GenerationJob:
        """Poll a job until it succeeds, fails, or times out.
        
        Args:
            job_id: The job ID returned by generate()
            poll_interval: Seconds between polls (uses config default)
            max_retries: Maximum poll attempts (uses config default)
            on_poll: Optional async callback(attempt, max_retries) for progress updates
        
        Returns:
            GenerationJob with final status
        
        Raises:
            TimeoutError: If max_retries exceeded
            RuntimeError: If job failed
        """
        if poll_interval is None:
            poll_interval = self._poll_config.get(f"{self.model_key.split('_')[0]}_interval", 45)
        if max_retries is None:
            max_retries = self._poll_config.get("max_retries", 30)

        backoff_factor = self._poll_config.get("backoff_factor", 1.5)

        for attempt in range(1, max_retries + 1):
            logger.debug(f"Polling {self.model_key} job {job_id}: attempt {attempt}/{max_retries}")

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

            # Still pending/processing — wait with slight backoff
            wait = min(poll_interval * (backoff_factor ** (attempt - 1)), 120)
            logger.debug(f"Job {job_id} status={job.status}, waiting {wait:.0f}s")
            await asyncio.sleep(wait)

        raise TimeoutError(
            f"Job {job_id} timed out after {max_retries} polling attempts "
            f"({max_retries * poll_interval / 60:.1f} min)"
        )

    # ── Full generate-and-download ────────────────────────────────────────────────────────

    async def generate_and_download(
        self,
        prompt: str,
        duration: int,
        reference_image: Optional[str] = None,
        is_continuation: bool = False,
        aspect_ratio: str = "9:16",
        on_poll: Optional[callable] = None,
    ) -> GenerationResult:
        """Submit, poll, and download a video clip in one call.
        
        This is the primary method used by FrameChainer.
        
        Returns:
            GenerationResult with local video_path
        """
        start = time.time()

        logger.info(
            f"Submitting {self.model_key} job: duration={duration}s, "
            f"has_ref={reference_image is not None}, continuation={is_continuation}"
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
