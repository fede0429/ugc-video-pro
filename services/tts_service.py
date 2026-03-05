"""
services/tts_service.py
========================
Multi-language TTS service via KIE.AI (ElevenLabs models).

Supports three languages equally:
    - Italian (it) — current priority
    - Chinese (zh)
    - English (en)

Models available on KIE.AI:
    - elevenlabs/text-to-speech-turbo-2-5: Fast, $0.03/1000 chars
    - elevenlabs/text-to-speech-multilingual-v2: Best multilingual, $0.06/1000 chars
    - elevenlabs/v3-text-to-dialogue: Dialogue mode, $0.07/1000 chars
"""

import time
from pathlib import Path
from typing import Optional

from services.kie_gateway import KieGateway
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Voice presets per language
# ──────────────────────────────────────────────────────────────

# ElevenLabs voice IDs for natural-sounding narration
# These can be configured in config.yaml
DEFAULT_VOICES = {
    "it": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # ElevenLabs Italian voice
        "name": "Italian Female",
        "description": "Natural Italian female narrator",
    },
    "zh": {
        "voice_id": "ThT5KcBeYPX3keUQqHPh",  # ElevenLabs Chinese voice
        "name": "Chinese Female",
        "description": "Natural Chinese female narrator",
    },
    "en": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # ElevenLabs Rachel
        "name": "English Female (Rachel)",
        "description": "Natural English female narrator",
    },
}

# Model selection per language
TTS_MODELS = {
    "fast": "elevenlabs/text-to-speech-turbo-2-5",
    "quality": "elevenlabs/text-to-speech-multilingual-v2",
    "dialogue": "elevenlabs/v3-text-to-dialogue",
}


class TTSService:
    """
    Multi-language text-to-speech service using KIE.AI ElevenLabs models.

    Usage:
        tts = TTSService(config)
        audio_path = await tts.synthesize(
            text="Questo prodotto è incredibile",
            language="it",
            output_path="/tmp/narration_it.mp3"
        )
    """

    def __init__(self, config: dict):
        self.config = config
        self._gateway = KieGateway(config)

        tts_config = config.get("tts", {})
        self._default_model = tts_config.get("model", "quality")
        self._output_dir = Path(
            config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
        )
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Load custom voice IDs from config
        self._voices = {}
        voices_config = tts_config.get("voices", {})
        for lang in ("it", "zh", "en"):
            if lang in voices_config:
                self._voices[lang] = voices_config[lang]
            else:
                self._voices[lang] = DEFAULT_VOICES.get(lang, DEFAULT_VOICES["en"])

    async def synthesize(
        self,
        text: str,
        language: str = "it",
        output_path: Optional[str] = None,
        model_tier: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> str:
        """
        Synthesize text to speech audio.

        Args:
            text: Text to speak
            language: Language code ("it", "zh", "en")
            output_path: Optional output file path
            model_tier: "fast", "quality", or "dialogue"
            voice_id: Override voice ID

        Returns:
            Path to generated audio file (MP3)
        """
        if not text.strip():
            raise ValueError("Empty text for TTS synthesis")

        # Select model
        tier = model_tier or self._default_model
        kie_model = TTS_MODELS.get(tier, TTS_MODELS["quality"])

        # Select voice
        voice_config = self._voices.get(language, self._voices.get("en"))
        vid = voice_id or voice_config.get("voice_id", "")

        # Output path
        if not output_path:
            output_path = str(
                self._output_dir
                / f"tts_{language}_{int(time.time())}.mp3"
            )

        logger.info(
            f"TTS synthesize: lang={language}, model={kie_model}, "
            f"voice={vid}, text_len={len(text)} chars"
        )

        # Build input for KIE.AI
        input_params = {
            "text": text,
            "voice_id": vid,
        }

        # For dialogue model, use different input format
        if tier == "dialogue":
            input_params["model_id"] = "eleven_v3"
        else:
            input_params["model_id"] = (
                "eleven_turbo_v2_5" if tier == "fast"
                else "eleven_multilingual_v2"
            )

        # Submit task
        task = await self._gateway.create_task(kie_model, input_params)

        # Wait for completion
        result = await self._gateway.wait_for_task(
            task.task_id,
            poll_interval=5,
            max_retries=60,
        )

        if not result.result_urls:
            raise RuntimeError(
                f"TTS task {task.task_id} completed but no audio URL"
            )

        # Download audio
        audio_path = await self._gateway.download(
            result.result_urls[0], output_path
        )

        logger.info(f"TTS audio generated: {audio_path}")
        return audio_path

    async def synthesize_segments(
        self,
        segments: list[dict],
        language: str = "it",
        model_tier: Optional[str] = None,
    ) -> list[str]:
        """
        Synthesize multiple text segments to audio files.

        Args:
            segments: List of {"text": "...", "segment_index": 0}
            language: Language code
            model_tier: Model tier override

        Returns:
            List of audio file paths (in order)
        """
        audio_paths = []

        for seg in segments:
            text = seg.get("text", "")
            idx = seg.get("segment_index", len(audio_paths))

            if not text.strip():
                logger.warning(f"Empty text for segment {idx}, skipping")
                continue

            output_path = str(
                self._output_dir
                / f"tts_{language}_seg{idx:02d}_{int(time.time())}.mp3"
            )

            try:
                path = await self.synthesize(
                    text=text,
                    language=language,
                    output_path=output_path,
                    model_tier=model_tier,
                )
                audio_paths.append(path)
            except Exception as e:
                logger.error(f"TTS failed for segment {idx}: {e}")
                raise

        logger.info(
            f"TTS batch complete: {len(audio_paths)} segments, lang={language}"
        )
        return audio_paths
