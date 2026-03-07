
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from models.kie_video import KieVideoAdapter
from models.base import GenerationJob
from .models import StoryBible, CharacterBible, ShotPlan


SEEDANCE_VALID_DURATIONS = [4, 5, 8, 10, 12]


class KieSeedanceAnimationAdapter:
    def __init__(self, config: dict, model_variant: str = "seedance_2", fallback_model: str = "seedance_15"):
        self.config = config
        self.requested_model = model_variant
        self.fallback_model = fallback_model
        selected = model_variant
        try:
            self.adapter = KieVideoAdapter(config, model_variant=model_variant)
        except Exception:
            self.adapter = KieVideoAdapter(config, model_variant=fallback_model)
            selected = fallback_model
        self.model_variant = selected

    @staticmethod
    def normalize_duration(seconds: float) -> int:
        seconds = max(4.0, float(seconds))
        best = min(SEEDANCE_VALID_DURATIONS, key=lambda x: abs(x - seconds))
        return int(best)

    def build_render_prompt(
        self,
        story_bible: StoryBible,
        characters: list[CharacterBible],
        shot: ShotPlan,
        scene_title: str,
    ) -> str:
        anchors = []
        for c in characters[:3]:
            char_anchor = ", ".join(filter(None, c.appearance[:4] + c.wardrobe[:2]))
            if char_anchor:
                anchors.append(f"{c.name}: {char_anchor}")
        continuity = "; ".join(shot.continuity_notes[:6])
        state_blob = "; ".join(f"{s.get('character_name')}={s.get('state_id')}:{s.get('objective')}" for s in getattr(shot, "state_assignments", [])[:3])
        asset_blob = "; ".join(a.get("prompt_anchor", "") for a in getattr(shot, "scene_assets", [])[:3] if a.get("prompt_anchor"))
        camera = f"camera {shot.camera}, framing {shot.framing}"
        emotion = shot.emotion
        template_id = shot.template_id or "custom"
        negative = shot.negative_prompt or "low consistency, bad anatomy, face drift"
        prompt = (
            f"{story_bible.visual_style}. Short-form vertical animation drama. "
            f"Scene {scene_title}. Shot template {template_id}. {camera}. Action: {shot.action}. "
            f"Emotion: {emotion}. Dialogue context: {shot.dialogue}. "
            f"Character anchors: {' | '.join(anchors)}. "
            f"Continuity notes: {continuity}. Character states: {state_blob}. Scene assets: {asset_blob}. "
            f"Keep face consistency, outfit consistency, cinematic motion, clean anatomy, expressive acting. "
            f"Avoid: {negative}."
        )
        return " ".join(prompt.split())

    async def generate_shot_job(
        self,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str = "9:16",
        reference_image: Optional[str] = None,
    ) -> str:
        render_seconds = self.normalize_duration(duration_seconds)
        return await self.adapter.generate(
            prompt=prompt,
            duration=render_seconds,
            reference_image=reference_image,
            aspect_ratio=aspect_ratio,
        )

    async def wait_for_completion(
        self,
        job_id: str,
        timeout_seconds: int = 1800,
        poll_interval: int = 15,
    ) -> GenerationJob:
        waited = 0
        while waited <= timeout_seconds:
            job = await self.adapter.poll_status(job_id)
            if job.status in ("succeeded", "failed"):
                return job
            await asyncio.sleep(poll_interval)
            waited += poll_interval
        return GenerationJob(
            job_id=job_id,
            model_name=self.model_variant,
            prompt="",
            duration=0,
            reference_image=None,
            submitted_at=0,
            status="failed",
            error=f"Timeout after {timeout_seconds}s",
        )

    async def download_result(self, job: GenerationJob, output_dir: str) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.adapter.output_dir = Path(output_dir)
        return await self.adapter.download(job)
