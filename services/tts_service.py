"""
services/tts_service.py
========================
Segment-based voice engine for the UGC pipeline.

Two APIs:
    synthesize_segments(task_id, timeline, voice_preset, language)
        → list[AudioSegmentAsset]          NEW (PDF blueprint)

    synthesize_timeline_segments(task_id, timeline, file_store, ...)
        → list[AudioSegmentAsset]          backward-compat alias

    synthesize(text, language, output_path, ...)
        → str  (audio path)                legacy single-text

    synthesize_segments(segments: list[dict], ...)
        → list[str]                        legacy batch

Audio is generated per A-roll segment so lipsync and timeline editing
can align clips to exact speech durations.
"""
from __future__ import annotations
import asyncio, time
from pathlib import Path
from typing import Optional

from core.timeline_types import AudioSegmentAsset, TimelineScript
from services.kie_gateway import KieGateway
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_VOICES = {
    "it": {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Italian Female"},
    "zh": {"voice_id": "ThT5KcBeYPX3keUQqHPh", "name": "Chinese Female"},
    "en": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "English Female (Rachel)"},
}
TTS_MODELS = {
    "fast":     "elevenlabs/text-to-speech-turbo-2-5",
    "quality":  "elevenlabs/text-to-speech-multilingual-v2",
    "dialogue": "elevenlabs/v3-text-to-dialogue",
}


class TTSService:
    """
    Multi-language TTS backed by KIE.AI ElevenLabs.

    Can be constructed two ways:
        TTSService(config)                     # standard (config dict)
        TTSService(tts_provider, file_store, logger)  # PDF blueprint DI style
    """

    def __init__(self, config_or_provider, file_store=None, _logger=None):
        # Standard construction: TTSService(config_dict)
        if isinstance(config_or_provider, dict):
            config = config_or_provider
            self.config = config
            self._gateway = KieGateway(config)
            tts_config = config.get("tts", {})
            self._default_model = tts_config.get("model", "quality")
            self._output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
            self._output_dir.mkdir(parents=True, exist_ok=True)
            voices_config = tts_config.get("voices", {})
            self._voices = {
                lang: voices_config.get(lang, DEFAULT_VOICES.get(lang, DEFAULT_VOICES["en"]))
                for lang in ("it", "zh", "en")
            }
            self._tts_provider = None
            self._file_store = None
            self._log = logger
        else:
            # DI construction: TTSService(tts_provider, file_store, logger)
            self._tts_provider = config_or_provider
            self._file_store = file_store
            self._log = _logger or logger
            self.config = {}
            self._gateway = None
            self._voices = DEFAULT_VOICES
            self._default_model = "quality"

    # ════════════════════════════════════════════════════════════════════════
    # NEW: PDF blueprint API — synthesize_segments(task_id, timeline, ...)
    # ════════════════════════════════════════════════════════════════════════

    async def synthesize_segments(
        self,
        task_id: str,
        timeline: TimelineScript,
        voice_preset: str,
        language: str,
        file_store=None,
    ) -> list[AudioSegmentAsset]:
        """
        Generate TTS audio for every A-roll segment.
        Matches the exact PDF blueprint signature.

        Args:
            task_id:      task identifier
            timeline:     TimelineScript with a_roll_segments
            voice_preset: language code — 'it' | 'zh' | 'en'
            language:     same as voice_preset (explicit for clarity)
            file_store:   FileStore (required — holds segment_audio_path())
        """
        store = file_store or self._file_store
        if store is None:
            raise ValueError("TTSService.synthesize_segments() requires a file_store")

        outputs: list[AudioSegmentAsset] = []
        a_roll_segs = [s for s in timeline.segments if s.track_type == "a_roll"]
        a_roll_segs.sort(key=lambda s: s.segment_index)

        for segment in a_roll_segs:
            text = (segment.spoken_line or "").strip()
            if not text:
                continue

            output_path = store.segment_audio_path(task_id, segment.segment_id)
            emotion_style = self._map_emotion_to_style(segment.emotion)

            try:
                audio_path = await self._synthesize_one(
                    text=text,
                    language=language or voice_preset,
                    output_path=output_path,
                    emotion_style=emotion_style,
                )
                duration = await self._probe_duration(audio_path)
                outputs.append(AudioSegmentAsset(
                    segment_id=segment.segment_id,
                    audio_path=audio_path,
                    duration_seconds=duration,
                    language=language,
                ))
                logger.info(
                    "audio segment synthesized",
                    extra={
                        "task_id": task_id,
                        "segment_id": segment.segment_id,
                        "output_path": output_path,
                    },
                )
            except Exception as e:
                logger.error(f"[task={task_id}] TTS failed for {segment.segment_id}: {e}")
                raise

        logger.info(f"[task={task_id}] TTS complete: {len(outputs)} segments")
        return outputs

    async def merge_segments(
        self,
        task_id: str,
        audio_segments: list[AudioSegmentAsset],
        ffmpeg_tools,
        file_store=None,
    ) -> str:
        """Merge all audio segments into one contiguous voice track."""
        store = file_store or self._file_store
        ordered_paths = [
            item.audio_path
            for item in sorted(audio_segments, key=lambda x: x.segment_id)
            if Path(item.audio_path).exists()
        ]
        output_path = (store or ffmpeg_tools).final_audio_path(task_id) if store else f"/tmp/{task_id}_voice.wav"
        await ffmpeg_tools.concat_audio_clips(
            input_paths=ordered_paths,
            output_path=output_path,
        )
        return output_path

    def _map_emotion_to_style(self, emotion: str) -> str:
        """Map segment emotion label to TTS speaking style."""
        normalized = (emotion or "").lower()
        if any(k in normalized for k in ("surprise", "excited", "excited_discovery")):
            return "energetic"
        if any(k in normalized for k in ("authentic", "casual", "warm")):
            return "conversational"
        if any(k in normalized for k in ("serious", "professional", "confident")):
            return "confident"
        if any(k in normalized for k in ("luxury", "elegant", "poised")):
            return "soft"
        return "natural"

    # ════════════════════════════════════════════════════════════════════════
    # Backward-compat: synthesize_timeline_segments(task_id, timeline, file_store)
    # ════════════════════════════════════════════════════════════════════════

    async def synthesize_timeline_segments(
        self,
        task_id: str,
        timeline: TimelineScript,
        file_store,
        model_tier: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> list[AudioSegmentAsset]:
        """
        Backward-compat shim for old tasks.py call signature.
        Delegates to synthesize_segments().
        """
        language = timeline.language.split(",")[0]
        return await self.synthesize_segments(
            task_id=task_id,
            timeline=timeline,
            voice_preset=language,
            language=language,
            file_store=file_store,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Core: single synthesis call
    # ════════════════════════════════════════════════════════════════════════

    async def _synthesize_one(
        self,
        text: str,
        language: str,
        output_path: str,
        model_tier: Optional[str] = None,
        voice_id: Optional[str] = None,
        emotion_style: str = "natural",
    ) -> str:
        """Generate one audio file. Returns the output_path."""
        # Use DI provider if available
        if self._tts_provider is not None:
            result = await self._tts_provider.synthesize(
                text=text,
                voice_preset=language,
                language=language,
                style=emotion_style,
                output_path=output_path,
            )
            return result.get("path", output_path)

        # Standard KIE.AI gateway path
        voice = self._get_voice(language, voice_id)
        model = TTS_MODELS.get(model_tier or self._default_model, TTS_MODELS["quality"])

        logger.debug(f"TTS: model={model} voice={voice} text[:60]={text[:60]!r}")

        response = await self._gateway.tts(
            text=text,
            voice_id=voice,
            model=model,
        )

        audio_url = response.get("audio_url") or response.get("url", "")
        if not audio_url:
            raise RuntimeError(f"TTS returned no audio URL: {response}")

        # Download audio
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        await self._gateway.download_file(audio_url, output_path)
        return output_path

    # ════════════════════════════════════════════════════════════════════════
    # Legacy: synthesize(text, ...) → str
    # ════════════════════════════════════════════════════════════════════════

    async def synthesize(
        self,
        text: str,
        language: str = "it",
        output_path: Optional[str] = None,
        model_tier: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> str:
        if not output_path:
            output_path = str(self._output_dir / f"tts_{int(time.time()*1000)}.mp3")
        return await self._synthesize_one(
            text=text, language=language,
            output_path=output_path, model_tier=model_tier, voice_id=voice_id,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Legacy: synthesize_segments(list[dict]) → list[str]
    # ════════════════════════════════════════════════════════════════════════

    async def _legacy_synthesize_segments(
        self,
        segments: list[dict],
        language: str = "it",
        model_tier: Optional[str] = None,
    ) -> list[str]:
        audio_paths: list[str] = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            if not text.strip():
                continue
            out = str(self._output_dir / f"seg_{i:03d}_{int(time.time()*1000)}.mp3")
            try:
                path = await self.synthesize(text=text, language=language, output_path=out, model_tier=model_tier)
                audio_paths.append(path)
                logger.info(f"TTS segment {i}: {path}")
            except Exception as e:
                logger.error(f"TTS segment {i} failed: {e}")
        return audio_paths

    # ── Voice lookup ─────────────────────────────────────────────────────────

    def _get_voice(self, language: str, override_id: Optional[str] = None) -> str:
        if override_id:
            return override_id
        voice_config = self._voices.get(language, self._voices["it"])
        return voice_config.get("voice_id") or DEFAULT_VOICES["it"]["voice_id"]

    async def _probe_duration(self, audio_path: str) -> float:
        try:
            import json as _j
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            return float(_j.loads(stdout.decode())["format"]["duration"])
        except Exception:
            return 0.0
