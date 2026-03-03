"""
core/video_stitcher.py
======================
FFmpeg-based video stitching engine for UGC Video Pro.

Combines multiple video clips into a single output with optional transitions:
    - cut: Simple concatenation (fastest, no transition)
    - crossfade: Smooth dissolve between clips (default)
    - fade: Fade to black + fade in
    - dissolve: xfade dissolve filter
"""

import os
import time
from pathlib import Path
from typing import Optional

from utils.ffmpeg_tools import FFmpegTools
from utils.logger import get_logger

logger = get_logger(__name__)


class VideoStitcher:
    """
    Stitch multiple video segments into a final output video.
    
    Supports multiple transition types and handles edge cases like
    mismatched resolutions by normalizing before stitching.
    """

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
        """
        Stitch multiple video clips into a single output file.
        
        Returns:
            Path to the final stitched video file
        """
        if not video_paths:
            raise ValueError("No video paths provided for stitching")

        if len(video_paths) == 1:
            logger.info(f"Single clip, no stitching needed: {video_paths[0]}")
            return video_paths[0]

        transition = transition or self.transition_type
        transition_duration = transition_duration if transition_duration is not None else self.transition_duration

        if not output_path:
            output_path = str(
                self.output_dir / f"ugc_final_{int(time.time())}.mp4"
            )

        logger.info(
            f"Stitching {len(video_paths)} clips, "
            f"transition={transition}, t_dur={transition_duration}s → {output_path}"
        )

        normalized_paths = await self._normalize_clips(video_paths)

        if transition == "cut":
            await self._stitch_concat(normalized_paths, output_path)
        elif transition in ("crossfade", "dissolve"):
            try:
                await self._stitch_xfade(
                    normalized_paths, output_path, transition_duration, transition
                )
            except Exception as e:
                logger.warning(f"xfade stitching failed ({e}), falling back to concat")
                await self._stitch_concat(normalized_paths, output_path)
        elif transition == "fade":
            try:
                await self._stitch_fade(normalized_paths, output_path, transition_duration)
            except Exception as e:
                logger.warning(f"fade stitching failed ({e}), falling back to concat")
                await self._stitch_concat(normalized_paths, output_path)
        else:
            logger.warning(f"Unknown transition '{transition}', using concat")
            await self._stitch_concat(normalized_paths, output_path)

        if not Path(output_path).exists():
            raise RuntimeError(f"Stitching produced no output at {output_path}")

        file_size = Path(output_path).stat().st_size
        duration = await self.ffmpeg.get_duration(output_path)
        logger.info(
            f"Stitched video: {output_path} "
            f"({file_size / 1024 / 1024:.1f} MB, {duration:.1f}s)"
        )

        for norm_path, orig_path in zip(normalized_paths, video_paths):
            if norm_path != orig_path and Path(norm_path).exists():
                try:
                    os.unlink(norm_path)
                except Exception:
                    pass

        return output_path

    async def _normalize_clips(self, video_paths: list[str]) -> list[str]:
        """Normalize all clips to same codec, resolution, and framerate."""
        normalized = []
        for path in video_paths:
            probe = await self.ffmpeg.probe_video(path)
            needs_normalization = False

            vcodec = probe.get("video_codec", "")
            pix_fmt = probe.get("pix_fmt", "")

            if vcodec != "h264" or pix_fmt != "yuv420p":
                needs_normalization = True

            if needs_normalization:
                norm_path = path.replace(".mp4", "_norm.mp4")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", path,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "44100",
                    norm_path,
                ]
                success, _, stderr = await self.ffmpeg.run_command(cmd, timeout=120)
                if success and Path(norm_path).exists():
                    normalized.append(norm_path)
                else:
                    logger.warning(f"Normalization failed for {path}, using original")
                    normalized.append(path)
            else:
                normalized.append(path)

        return normalized

    async def _stitch_concat(self, video_paths: list[str], output_path: str) -> None:
        """Simple concatenation without transitions using concat demuxer."""
        concat_file = str(self.output_dir / f"concat_{int(time.time())}.txt")
        try:
            with open(concat_file, "w") as f:
                for path in video_paths:
                    escaped = str(path).replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ]

            success, stdout, stderr = await self.ffmpeg.run_command(cmd, timeout=300)

            if not success:
                raise RuntimeError(f"ffmpeg concat failed: {stderr[:500]}")

        finally:
            if Path(concat_file).exists():
                os.unlink(concat_file)

    async def _stitch_xfade(
        self,
        video_paths: list[str],
        output_path: str,
        transition_duration: float,
        transition_type: str = "dissolve",
    ) -> None:
        """Stitch clips with xfade crossfade transitions."""
        durations = []
        for path in video_paths:
            dur = await self.ffmpeg.get_duration(path)
            durations.append(dur)

        n = len(video_paths)
        xfade_transition = "fade" if transition_type == "fade" else "dissolve"

        inputs = []
        for path in video_paths:
            inputs.extend(["-i", path])

        filter_parts = []
        cumulative_offset = 0.0
        prev_v = "[0:v]"
        prev_a = "[0:a]"

        for i in range(1, n):
            cumulative_offset += durations[i - 1] - transition_duration
            offset = max(0.0, cumulative_offset)

            out_v = f"[v{i}]" if i < n - 1 else "[vout]"
            out_a = f"[a{i}]" if i < n - 1 else "[aout]"

            filter_parts.append(
                f"{prev_v}[{i}:v]xfade=transition={xfade_transition}"
                f":duration={transition_duration}:offset={offset:.3f}{out_v}"
            )
            filter_parts.append(
                f"{prev_a}[{i}:a]acrossfade=d={transition_duration}{out_a}"
            )

            prev_v = out_v
            prev_a = out_a

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

        success, stdout, stderr = await self.ffmpeg.run_command(cmd, timeout=600)

        if not success:
            raise RuntimeError(f"xfade stitching failed: {stderr[:500]}")

    async def _stitch_fade(
        self,
        video_paths: list[str],
        output_path: str,
        fade_duration: float,
    ) -> None:
        """Stitch clips with fade-to-black / fade-from-black transitions."""
        faded_paths = []
        temp_files = []

        try:
            for i, path in enumerate(video_paths):
                duration = await self.ffmpeg.get_duration(path)
                fade_out_start = max(0, duration - fade_duration)
                faded_path = path.replace(".mp4", f"_fade_{i}.mp4")
                temp_files.append(faded_path)

                cmd = [
                    "ffmpeg", "-y",
                    "-i", path,
                    "-vf", (
                        f"fade=t=in:st=0:d={fade_duration},"
                        f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration}"
                    ),
                    "-af", (
                        f"afade=t=in:st=0:d={fade_duration},"
                        f"afade=t=out:st={fade_out_start:.3f}:d={fade_duration}"
                    ),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    faded_path,
                ]

                success, _, stderr = await self.ffmpeg.run_command(cmd, timeout=120)
                if not success:
                    raise RuntimeError(f"Fade processing failed: {stderr[:300]}")
                faded_paths.append(faded_path)

            await self._stitch_concat(faded_paths, output_path)

        finally:
            for tmp in temp_files:
                if Path(tmp).exists():
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
