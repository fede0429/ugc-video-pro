"""
services/lipsync_service.py
============================
AI lip-sync service. Two APIs:
    generate()              -> single face+audio -> video (legacy)
    render_a_roll_segments() -> TimelineScript + AudioSegmentAsset[] -> RenderedAsset[] (new)
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional

from core.timeline_types import AudioSegmentAsset, PresenterProfile, RenderedAsset, TimelineScript
from services.kie_gateway import KieGateway
from utils.logger import get_logger

logger = get_logger(__name__)

LIPSYNC_MODELS = {
    "kling_avatar_720p":  {"kie_model": "kling-ai/avatar", "resolution": "720p",  "max_duration": 15, "price_per_sec": 0.04},
    "kling_avatar_1080p": {"kie_model": "kling-ai/avatar", "resolution": "1080p", "max_duration": 15, "price_per_sec": 0.08},
    "infinitetalk_480p":  {"kie_model": "meigen-ai/infinitetalk", "resolution": "480p", "max_duration": 15, "price_per_sec": 0.015},
    "infinitetalk_720p":  {"kie_model": "meigen-ai/infinitetalk", "resolution": "720p", "max_duration": 15, "price_per_sec": 0.06},
    "none":               None,
}


class LipSyncService:
    def __init__(self, config: dict):
        self.config = config
        self._gateway = KieGateway(config)
        lipsync_config = config.get("lipsync", {})
        self._default_model = lipsync_config.get("model", "kling_avatar_720p")
        self._output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── NEW ──────────────────────────────────────────────────────
    async def render_a_roll_segments(
        self,
        task_id: str,
        timeline: TimelineScript,
        presenter_profile: PresenterProfile,
        audio_assets: list[AudioSegmentAsset],
        file_store,
    ) -> list[RenderedAsset]:
        """
        Render lipsync video for every A-roll segment that has audio.
        Returns a RenderedAsset for each successfully rendered segment.
        If presenter has no face image or lipsync_model == 'none', returns [].
        """
        if (
            not presenter_profile.face_image_path
            or presenter_profile.lipsync_model == "none"
        ):
            logger.info(f"[task={task_id}] Lipsync disabled (no face image or model=none)")
            return []

        audio_map = {a.segment_id: a for a in audio_assets}
        results: list[RenderedAsset] = []

        for segment in sorted(timeline.a_roll_segments, key=lambda s: s.segment_index):
            audio_asset = audio_map.get(segment.segment_id)
            if not audio_asset:
                logger.warning(f"[task={task_id}] No audio for A-roll {segment.segment_id}")
                continue

            output_path = file_store.a_roll_path(task_id, segment.segment_id)
            try:
                video_path = await self.generate(
                    face_image=presenter_profile.face_image_path,
                    audio_path=audio_asset.audio_path,
                    output_path=output_path,
                    model=presenter_profile.lipsync_model,
                )
                results.append(RenderedAsset(
                    segment_id=segment.segment_id,
                    video_path=video_path,
                    duration_seconds=audio_asset.duration_seconds,
                    track_type="a_roll",
                ))
                logger.info(f"[task={task_id}] A-roll rendered: {segment.segment_id}")
            except Exception as e:
                logger.error(f"[task={task_id}] Lipsync failed {segment.segment_id}: {e}")
                raise

        logger.info(f"[task={task_id}] A-roll done: {len(results)} clips")
        return results

    # ── LEGACY ───────────────────────────────────────────────────
    async def generate(
        self,
        face_image: str,
        audio_path: str,
        output_path: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        model_key = model or self._default_model
        if model_key not in LIPSYNC_MODELS or LIPSYNC_MODELS[model_key] is None:
            raise ValueError(f"Unknown/disabled lipsync model: {model_key}")

        model_config = LIPSYNC_MODELS[model_key]
        kie_model = model_config["kie_model"]
        if not output_path:
            output_path = str(self._output_dir / f"lipsync_{model_key}_{int(time.time())}.mp4")

        logger.info(f"Lipsync: model={model_key}")
        input_params = {"resolution": model_config["resolution"]}

        # Encode face image
        if face_image.startswith(("http://", "https://")):
            input_params["input_face_url"] = face_image
        else:
            import base64
            with open(face_image, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            suffix = Path(face_image).suffix.lower()
            mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            input_params["input_face_url"] = f"data:{mime};base64,{b64}"

        # Encode audio
        if audio_path.startswith(("http://", "https://")):
            input_params["input_audio_url"] = audio_path
        else:
            import base64
            with open(audio_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}
            mime = mime_map.get(Path(audio_path).suffix.lower(), "audio/mpeg")
            input_params["input_audio_url"] = f"data:{mime};base64,{b64}"

        task = await self._gateway.create_task(kie_model, input_params)
        result = await self._gateway.wait_for_task(task.task_id, poll_interval=10, max_retries=90)
        if not result.result_urls:
            raise RuntimeError(f"Lipsync task {task.task_id} no video URL")
        video_path = await self._gateway.download(result.result_urls[0], output_path)
        logger.info(f"Lipsync video: {video_path}")
        return video_path
