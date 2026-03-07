"""
services/subtitle_service.py
=============================
Generates subtitle files from a TimelineScript + AudioSegmentAsset list.
"""
from __future__ import annotations

from core.timeline_types import AudioSegmentAsset, TimelineScript
from utils.file_store import FileStore
from utils.logger import get_logger
from utils.timecode import seconds_to_srt_timestamp


class SubtitleService:
    def __init__(self, config_or_store, logger=None):
        if isinstance(config_or_store, dict):
            self.file_store = FileStore(config_or_store)
            self.logger = logger or get_logger(__name__)
        else:
            self.file_store = config_or_store
            self.logger = logger or get_logger(__name__)

    async def generate_srt(
        self,
        task_id: str,
        timeline: TimelineScript,
        audio_assets: list[AudioSegmentAsset],
    ) -> str:
        subtitle_path = self.file_store.subtitle_path(task_id, extension="srt")
        audio_map = {item.segment_id: item for item in audio_assets}
        lines: list[str] = []
        cursor = 0.0
        index = 1

        for segment in sorted(timeline.segments, key=lambda x: x.segment_index):
            if segment.track_type != "a_roll":
                duration = float(segment.duration_seconds)
                if (segment.overlay_text or "").strip():
                    start_ts = seconds_to_srt_timestamp(cursor)
                    end_ts = seconds_to_srt_timestamp(cursor + duration)
                    lines.append(str(index))
                    lines.append(f"{start_ts} --> {end_ts}")
                    lines.append(segment.overlay_text.strip())
                    lines.append("")
                    index += 1
                cursor += duration
                continue

            audio_asset = audio_map.get(segment.segment_id)
            duration = float(audio_asset.duration_seconds if audio_asset else segment.duration_seconds)
            text = (segment.spoken_line or segment.overlay_text or "").strip()
            if text:
                start_ts = seconds_to_srt_timestamp(cursor)
                end_ts = seconds_to_srt_timestamp(cursor + duration)
                lines.append(str(index))
                lines.append(f"{start_ts} --> {end_ts}")
                lines.append(text)
                lines.append("")
                index += 1
            cursor += duration

        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

        self.logger.info("subtitle file generated", extra={"task_id": task_id, "subtitle_path": subtitle_path})
        return subtitle_path
