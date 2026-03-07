"""
core/video_stitcher.py
======================
FFmpeg-based video stitching + timeline composer.

Two APIs:
    stitch()   -> legacy list[str] paths -> output.mp4 (unchanged)
    compose()  -> TimelineComposer.compose() using assemble_timeline (new)
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional

from core.timeline_types import (
    AudioSegmentAsset,
    RenderedAsset,
    TimelineScript,
)
from utils.ffmpeg_tools import FFmpegTools
from utils.logger import get_logger

logger = get_logger(__name__)


class VideoStitcher:
    """Stitch multiple video segments into a final output (legacy API)."""

    def __init__(self, config: dict):
        self.config = config
        self.ffmpeg = FFmpegTools(config)
        video_config = config.get("video", {})
        self.output_dir = Path(video_config.get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.transition_type = video_config.get("transition_type", "crossfade")
        self.transition_duration = float(video_config.get("transition_duration", 0.3))

    async def stitch(
        self,
        video_paths: list[str],
        transition: Optional[str] = None,
        transition_duration: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> str:
        if not video_paths:
            raise ValueError("No video paths for stitching")
        if len(video_paths) == 1:
            return video_paths[0]

        transition = transition or self.transition_type
        td = transition_duration if transition_duration is not None else self.transition_duration

        if not output_path:
            output_path = str(self.output_dir / f"ugc_final_{int(time.time())}.mp4")

        logger.info(f"Stitching {len(video_paths)} clips, transition={transition} → {output_path}")
        normalized = await self._normalize_clips(video_paths)

        if transition == "cut":
            await self._stitch_concat(normalized, output_path)
        elif transition in ("crossfade", "dissolve"):
            try:
                await self._stitch_xfade(normalized, output_path, td, transition)
            except Exception as e:
                logger.warning(f"xfade failed ({e}), falling back to concat")
                await self._stitch_concat(normalized, output_path)
        elif transition == "fade":
            try:
                await self._stitch_fade(normalized, output_path, td)
            except Exception as e:
                logger.warning(f"fade failed ({e}), falling back to concat")
                await self._stitch_concat(normalized, output_path)
        else:
            await self._stitch_concat(normalized, output_path)

        if not Path(output_path).exists():
            raise RuntimeError(f"Stitching produced no output at {output_path}")

        size = Path(output_path).stat().st_size
        duration = await self.ffmpeg.get_duration(output_path)
        logger.info(f"Stitched: {output_path} ({size/1024/1024:.1f}MB, {duration:.1f}s)")

        for norm_path, orig_path in zip(normalized, video_paths):
            if norm_path != orig_path and Path(norm_path).exists():
                try:
                    os.unlink(norm_path)
                except Exception:
                    pass
        return output_path

    async def _normalize_clips(self, video_paths: list[str]) -> list[str]:
        normalized = []
        for path in video_paths:
            probe = await self.ffmpeg.probe_video(path)
            if probe.get("video_codec") != "h264" or probe.get("pix_fmt") != "yuv420p":
                norm_path = path.replace(".mp4", "_norm.mp4")
                cmd = ["ffmpeg", "-y", "-i", path, "-c:v", "libx264", "-preset", "fast",
                       "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac",
                       "-b:a", "128k", "-ar", "44100", norm_path]
                success, _, _ = await self.ffmpeg.run_command(cmd, timeout=120)
                normalized.append(norm_path if success and Path(norm_path).exists() else path)
            else:
                normalized.append(path)
        return normalized

    async def _stitch_concat(self, video_paths: list[str], output_path: str) -> None:
        concat_file = str(self.output_dir / f"concat_{int(time.time())}.txt")
        try:
            with open(concat_file, "w") as f:
                for path in video_paths:
                    f.write(f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                   "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", output_path]
            success, _, stderr = await self.ffmpeg.run_command(cmd, timeout=300)
            if not success:
                raise RuntimeError(f"ffmpeg concat failed: {stderr[:500]}")
        finally:
            if Path(concat_file).exists():
                os.unlink(concat_file)

    async def _stitch_xfade(
        self, video_paths: list[str], output_path: str,
        transition_duration: float, transition_type: str = "dissolve",
    ) -> None:
        durations = [await self.ffmpeg.get_duration(p) for p in video_paths]
        n = len(video_paths)
        inputs = []
        for p in video_paths:
            inputs.extend(["-i", p])

        filter_parts = []
        cumulative = 0.0
        prev_v, prev_a = "[0:v]", "[0:a]"
        xfade_t = "fade" if transition_type == "fade" else "dissolve"

        for i in range(1, n):
            cumulative += durations[i - 1] - transition_duration
            offset = max(0.0, cumulative)
            out_v = f"[v{i}]" if i < n - 1 else "[vout]"
            out_a = f"[a{i}]" if i < n - 1 else "[aout]"
            filter_parts.append(
                f"{prev_v}[{i}:v]xfade=transition={xfade_t}:duration={transition_duration}:offset={offset:.3f}{out_v}"
            )
            filter_parts.append(f"{prev_a}[{i}:a]acrossfade=d={transition_duration}{out_a}")
            prev_v, prev_a = out_v, out_a

        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts),
               "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "fast",
               "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", output_path]
        success, _, stderr = await self.ffmpeg.run_command(cmd, timeout=600)
        if not success:
            raise RuntimeError(f"xfade failed: {stderr[:500]}")

    async def _stitch_fade(
        self, video_paths: list[str], output_path: str, fade_duration: float,
    ) -> None:
        faded_paths, temp_files = [], []
        try:
            for i, path in enumerate(video_paths):
                duration = await self.ffmpeg.get_duration(path)
                fade_out_start = max(0, duration - fade_duration)
                faded_path = path.replace(".mp4", f"_fade_{i}.mp4")
                temp_files.append(faded_path)
                cmd = ["ffmpeg", "-y", "-i", path,
                       "-vf", f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={fade_out_start:.3f}:d={fade_duration}",
                       "-af", f"afade=t=in:st=0:d={fade_duration},afade=t=out:st={fade_out_start:.3f}:d={fade_duration}",
                       "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", faded_path]
                success, _, stderr = await self.ffmpeg.run_command(cmd, timeout=120)
                if not success:
                    raise RuntimeError(f"Fade failed: {stderr[:300]}")
                faded_paths.append(faded_path)
            await self._stitch_concat(faded_paths, output_path)
        finally:
            for tmp in temp_files:
                if Path(tmp).exists():
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass


class TimelineComposer:
    """
    New UGC pipeline: assemble the final video from A-roll + B-roll assets
    in timeline order, with subtitles, overlays, and optional BGM.
    """

    def __init__(self, config: dict):
        self.config = config
        self.ffmpeg = FFmpegTools(config)

    async def compose(
        self,
        task_id: str,
        timeline: TimelineScript,
        a_roll_assets: list[RenderedAsset],
        b_roll_assets: list[RenderedAsset],
        subtitle_path: Optional[str],
        bgm_path: Optional[str],
        file_store,
        overlay_plan: Optional[list[dict]] = None,
    ) -> str:
        """
        Assemble final video from rendered assets in timeline order.

        Returns: path to final_video.mp4
        """
        a_roll_map = {a.segment_id: a for a in a_roll_assets}
        b_roll_map = {b.segment_id: b for b in b_roll_assets}

        # Build ordered clip list
        ordered_clips: list[dict] = []
        for segment in sorted(timeline.segments, key=lambda s: s.segment_index):
            asset = (
                a_roll_map.get(segment.segment_id)
                or b_roll_map.get(segment.segment_id)
            )
            if asset:
                ordered_clips.append({"video_path": asset.video_path})
            else:
                logger.warning(
                    f"[task={task_id}] No rendered asset for segment "
                    f"{segment.segment_id} (track={segment.track_type}) — skipping"
                )

        if not ordered_clips:
            raise RuntimeError(f"[task={task_id}] No clips to assemble")

        # Build overlay plan from timeline overlay_text unless caller provides one
        overlay_plan = overlay_plan or self._build_overlay_plan(timeline, a_roll_assets, b_roll_assets)

        output_path = file_store.final_video_path(task_id)

        logger.info(
            f"[task={task_id}] Composing timeline: {len(ordered_clips)} clips, "
            f"subtitles={bool(subtitle_path)}, bgm={bool(bgm_path)}, "
            f"overlays={len(overlay_plan)}"
        )

        final_path = await self.ffmpeg.assemble_timeline(
            ordered_clips=ordered_clips,
            subtitle_path=subtitle_path,
            overlay_plan=overlay_plan,
            bgm_path=bgm_path,
            output_path=output_path,
        )

        logger.info(f"[task={task_id}] Timeline composed: {final_path}")
        return final_path

    def _build_overlay_plan(
        self,
        timeline: TimelineScript,
        a_roll_assets: list[RenderedAsset],
        b_roll_assets: list[RenderedAsset],
    ) -> list[dict]:
        """Build drawtext overlay plan from timeline overlay_text values."""
        a_map = {a.segment_id: a for a in a_roll_assets}
        b_map = {b.segment_id: b for b in b_roll_assets}

        plan: list[dict] = []
        cursor = 0.0

        for segment in sorted(timeline.segments, key=lambda s: s.segment_index):
            asset = a_map.get(segment.segment_id) or b_map.get(segment.segment_id)
            dur = asset.duration_seconds if asset else float(segment.duration_seconds)

            if segment.overlay_text.strip():
                plan.append({
                    "text": segment.overlay_text.strip(),
                    "start": cursor + 0.3,
                    "end": cursor + dur - 0.3,
                    "fontsize": 44,
                    "x": "(w-text_w)/2",
                    "y": "h*0.82",
                })
            cursor += dur

        return plan
