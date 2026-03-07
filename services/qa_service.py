"""
services/qa_service.py
=======================
Quality gate for pipeline outputs.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.timeline_types import AudioSegmentAsset, QAReport, QAIssue, RenderedAsset, TimelineScript
from utils.ffmpeg_tools import FFmpegTools
from utils.file_store import FileStore
from utils.logger import get_logger


class QAService:
    def __init__(self, config_or_file_store=None, ffmpeg_tools=None, logger=None):
        self.logger = logger or get_logger(__name__)
        self.file_store = None
        if isinstance(config_or_file_store, dict):
            self.file_store = FileStore(config_or_file_store)
            self.ffmpeg_tools = ffmpeg_tools or FFmpegTools(config_or_file_store)
        else:
            self.file_store = config_or_file_store
            self.ffmpeg_tools = ffmpeg_tools

    async def run(
        self,
        timeline: TimelineScript,
        final_video_path: str,
        subtitle_path: str | None,
        a_roll_assets: list[RenderedAsset],
        b_roll_assets: list[RenderedAsset],
        audio_assets: list[AudioSegmentAsset],
    ) -> QAReport:
        issues: list[QAIssue] = []
        self._check_a_roll_presence(issues, timeline, a_roll_assets)
        self._check_b_roll_presence(issues, timeline, b_roll_assets)
        self._check_audio_coverage(issues, timeline, audio_assets)
        self._check_subtitle_presence(issues, subtitle_path)
        self._check_final_video_exists(issues, final_video_path)
        await self._check_black_frames_if_possible(issues, final_video_path)

        checks = {
            "timeline_segments": len(timeline.segments),
            "a_roll_assets": len(a_roll_assets),
            "b_roll_assets": len(b_roll_assets),
            "audio_assets": len(audio_assets),
            "subtitle_exists": bool(subtitle_path and Path(subtitle_path).exists()),
            "final_video_exists": Path(final_video_path).exists(),
        }
        passed = not any(item.severity == "error" for item in issues)
        report = QAReport(passed=passed, issues=issues, checks=checks)

        if self.file_store:
            task_id = self._guess_task_id(final_video_path)
            if task_id:
                report_path = self.file_store.qa_report_path(task_id)
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        self.logger.info("qa completed", extra={"passed": passed, "issue_count": len(issues)})
        return report

    def _check_a_roll_presence(self, issues, timeline, a_roll_assets):
        required = [seg for seg in timeline.segments if seg.track_type == "a_roll"]
        if required and not a_roll_assets:
            issues.append(QAIssue(
                code="missing_a_roll", severity="error",
                message="timeline requires A-roll segments but none were rendered",
            ))

    def _check_b_roll_presence(self, issues, timeline, b_roll_assets):
        required = [seg for seg in timeline.segments if seg.track_type == "b_roll"]
        if required and not b_roll_assets:
            issues.append(QAIssue(
                code="missing_b_roll", severity="warning",
                message="timeline contains B-roll segments but no B-roll assets found",
            ))

    def _check_audio_coverage(self, issues, timeline, audio_assets):
        audio_segment_ids = {item.segment_id for item in audio_assets}
        for segment in timeline.segments:
            if segment.track_type != "a_roll":
                continue
            if (segment.spoken_line or "").strip() and segment.segment_id not in audio_segment_ids:
                issues.append(QAIssue(
                    code="missing_audio_segment", severity="error",
                    message=f"missing audio for segment {segment.segment_id}",
                    segment_id=segment.segment_id,
                ))

    def _check_subtitle_presence(self, issues, subtitle_path):
        if not subtitle_path or not Path(subtitle_path).exists():
            issues.append(QAIssue(
                code="missing_subtitles", severity="warning",
                message="subtitle file is missing",
            ))

    def _check_final_video_exists(self, issues, final_video_path):
        if not Path(final_video_path).exists():
            issues.append(QAIssue(
                code="missing_final_video", severity="error",
                message="final video file was not created",
            ))

    async def _check_black_frames_if_possible(self, issues, final_video_path):
        if not self.ffmpeg_tools or not Path(final_video_path).exists():
            return
        try:
            has_black = await self.ffmpeg_tools.detect_black_frames(final_video_path)
            if has_black:
                issues.append(QAIssue(
                    code="black_frames_detected", severity="warning",
                    message="potential black frames detected in final video",
                ))
        except Exception:
            pass

    def _guess_task_id(self, final_video_path: str) -> str | None:
        parts = Path(final_video_path).parts
        if "tasks" in parts:
            idx = parts.index("tasks")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None
