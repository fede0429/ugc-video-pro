"""
services/lipsync_service.py
============================
AI lip-sync service via KIE.AI.

Generates talking-head videos by synchronizing audio to a face image/video.

Models available on KIE.AI:
    - Kling AI Avatar (720p/1080p): $0.04-$0.08/sec, up to 15s
    - MeiGen-AI InfiniteTalk (480p/720p): $0.015-$0.06/sec, up to 15s
"""

import time
from pathlib import Path
from typing import Optional

from services.kie_gateway import KieGateway
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Lip-sync model registry
# ──────────────────────────────────────────────────────────────

LIPSYNC_MODELS = {
    "kling_avatar_720p": {
        "kie_model": "kling-ai/avatar",
        "resolution": "720p",
        "max_duration": 15,
        "price_per_sec": 0.04,
    },
    "kling_avatar_1080p": {
        "kie_model": "kling-ai/avatar",
        "resolution": "1080p",
        "max_duration": 15,
        "price_per_sec": 0.08,
    },
    "infinitetalk_480p": {
        "kie_model": "meigen-ai/infinitetalk",
        "resolution": "480p",
        "max_duration": 15,
        "price_per_sec": 0.015,
    },
    "infinitetalk_720p": {
        "kie_model": "meigen-ai/infinitetalk",
        "resolution": "720p",
        "max_duration": 15,
        "price_per_sec": 0.06,
    },
}


class LipSyncService:
    """
    AI lip-sync service — synchronize audio to a face.

    Usage:
        lipsync = LipSyncService(config)
        video_path = await lipsync.generate(
            face_image="/tmp/presenter.jpg",
            audio_path="/tmp/narration_it.mp3",
            output_path="/tmp/talking_head.mp4"
        )
    """

    def __init__(self, config: dict):
        self.config = config
        self._gateway = KieGateway(config)

        lipsync_config = config.get("lipsync", {})
        self._default_model = lipsync_config.get("model", "kling_avatar_720p")
        self._output_dir = Path(
            config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
        )
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        face_image: str,
        audio_path: str,
        output_path: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a lip-synced talking-head video.

        Args:
            face_image: Path to face image (or URL)
            audio_path: Path to audio file (or URL)
            output_path: Optional output video path
            model: Model key override

        Returns:
            Path to generated lip-synced video
        """
        model_key = model or self._default_model
        if model_key not in LIPSYNC_MODELS:
            raise ValueError(
                f"Unknown lip-sync model: {model_key}. "
                f"Available: {list(LIPSYNC_MODELS.keys())}"
            )

        model_config = LIPSYNC_MODELS[model_key]
        kie_model = model_config["kie_model"]

        if not output_path:
            output_path = str(
                self._output_dir
                / f"lipsync_{model_key}_{int(time.time())}.mp4"
            )

        logger.info(
            f"Lip-sync generate: model={model_key}, "
            f"face={face_image[:50]}, audio={audio_path[:50]}"
        )

        # Build input — face image and audio as URLs or base64
        input_params: dict = {
            "resolution": model_config["resolution"],
        }

        # Face image
        if face_image.startswith(("http://", "https://")):
            input_params["input_face_url"] = face_image
        else:
            import base64
            with open(face_image, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            suffix = Path(face_image).suffix.lower()
            mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            input_params["input_face_url"] = f"data:{mime};base64,{img_b64}"

        # Audio file
        if audio_path.startswith(("http://", "https://")):
            input_params["input_audio_url"] = audio_path
        else:
            import base64
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            suffix = Path(audio_path).suffix.lower()
            mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}
            mime = mime_map.get(suffix, "audio/mpeg")
            input_params["input_audio_url"] = f"data:{mime};base64,{audio_b64}"

        # Submit task
        task = await self._gateway.create_task(kie_model, input_params)

        # Wait for completion (lip-sync can take longer)
        result = await self._gateway.wait_for_task(
            task.task_id,
            poll_interval=10,
            max_retries=90,  # up to 15 min
        )

        if not result.result_urls:
            raise RuntimeError(
                f"Lip-sync task {task.task_id} completed but no video URL"
            )

        # Download video
        video_path = await self._gateway.download(
            result.result_urls[0], output_path
        )

        logger.info(f"Lip-sync video generated: {video_path}")
        return video_path
