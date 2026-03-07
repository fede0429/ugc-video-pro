"""
utils/ffmpeg_tools.py
=====================
Unified FFmpeg wrapper — merges the original config-based API (used by
VideoStitcher, FrameChainer) with the new timeline-assembly API
(used by TimelineComposer, QAService) from the Blueprint.

Both constructor signatures are supported:
    FFmpegTools(config: dict)               # legacy
    FFmpegTools(ffmpeg_bin, ffprobe_bin, logger)  # blueprint style (via class method)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 120
LONG_TIMEOUT = 600


class FFmpegTools:
    """Async wrapper around ffmpeg and ffprobe — legacy + timeline API unified."""

    def __init__(
        self,
        config_or_ffmpeg_bin=None,
        ffprobe_bin: str = "ffprobe",
        ext_logger=None,
    ):
        # Support both calling conventions:
        #   FFmpegTools(config_dict)
        #   FFmpegTools("ffmpeg", "ffprobe", logger)
        if isinstance(config_or_ffmpeg_bin, dict):
            config = config_or_ffmpeg_bin
            self.ffmpeg_bin = "ffmpeg"
            self.ffprobe_bin = "ffprobe"
            self.logger = ext_logger
            video_config = config.get("video", {})
            self.output_dir = Path(video_config.get("output_dir", "/tmp/ugc_videos"))
            self.video_codec = video_config.get("video_codec", "libx264")
            self.audio_codec = video_config.get("audio_codec", "aac")
            self.crf = str(video_config.get("crf", 23))
            self.preset = video_config.get("preset", "fast")
        else:
            self.ffmpeg_bin = config_or_ffmpeg_bin or "ffmpeg"
            self.ffprobe_bin = ffprobe_bin
            self.logger = ext_logger
            self.output_dir = Path("/tmp/ugc_videos")
            self.video_codec = "libx264"
            self.audio_codec = "aac"
            self.crf = "23"
            self.preset = "fast"

        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────
    # NEW Timeline Assembly API (from Blueprint)
    # ─────────────────────────────────────────────────────────────

    async def concat_audio_clips(self, input_paths: list[str], output_path: str) -> str:
        if not input_paths:
            raise ValueError("input_paths is empty")
        list_file = Path(output_path).with_suffix(".concat.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for path in input_paths:
                f.write(f"file '{Path(path).as_posix()}'\n")
        cmd = [self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
               "-i", str(list_file), "-c", "copy", output_path]
        await self._run(cmd)
        return output_path

    async def assemble_timeline(
        self,
        ordered_clips: list[dict],
        subtitle_path: str | None,
        overlay_plan: list[dict],
        bgm_path: str | None,
        output_path: str,
    ) -> str:
        if not ordered_clips:
            raise ValueError("ordered_clips is empty")

        temp_concat = str(Path(output_path).with_name("timeline_concat.txt"))
        with open(temp_concat, "w", encoding="utf-8") as f:
            for clip in ordered_clips:
                f.write(f"file '{Path(clip['video_path']).as_posix()}'\n")

        temp_joined = str(Path(output_path).with_name("joined.mp4"))
        await self._run([self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
                         "-i", temp_concat, "-c", "copy", temp_joined])

        current_input = temp_joined

        if subtitle_path and Path(subtitle_path).exists():
            subtitled = str(Path(output_path).with_name("subtitled.mp4"))
            await self.burn_subtitles(current_input, subtitle_path, subtitled)
            current_input = subtitled

        if overlay_plan:
            overlaid = str(Path(output_path).with_name("overlaid.mp4"))
            await self.overlay_text_blocks(current_input, overlay_plan, overlaid)
            current_input = overlaid

        if bgm_path and Path(bgm_path).exists():
            mixed = str(Path(output_path).with_name("with_bgm.mp4"))
            await self.mix_bgm(current_input, bgm_path, mixed)
            current_input = mixed

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(current_input).replace(output_path)
        return output_path

    async def burn_subtitles(self, input_video: str, subtitle_path: str, output_path: str) -> str:
        cmd = [self.ffmpeg_bin, "-y", "-i", input_video,
               "-vf", f"subtitles={subtitle_path}", "-c:a", "copy", output_path]
        await self._run(cmd)
        return output_path

    async def overlay_text_blocks(
        self, input_video: str, overlay_plan: list[dict], output_path: str
    ) -> str:
        if not overlay_plan:
            Path(input_video).replace(output_path)
            return output_path

        drawtexts: list[str] = []
        for item in overlay_plan:
            text = str(item.get("text", "")).replace(":", r"\:").replace("'", r"\'")
            start = float(item.get("start", 0.0))
            end = float(item.get("end", 0.0))
            x = item.get("x", "(w-text_w)/2")
            y = item.get("y", "h*0.78")
            fontsize = int(item.get("fontsize", 42))
            drawtexts.append(
                "drawtext="
                f"text='{text}':x={x}:y={y}:fontsize={fontsize}:"
                "fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=14:"
                f"enable='between(t,{start},{end})'"
            )
        cmd = [self.ffmpeg_bin, "-y", "-i", input_video,
               "-vf", ",".join(drawtexts), "-codec:a", "copy", output_path]
        await self._run(cmd)
        return output_path

    async def mix_bgm(self, input_video: str, bgm_path: str, output_path: str) -> str:
        cmd = [
            self.ffmpeg_bin, "-y", "-i", input_video, "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            "[1:a]volume=0.18[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
        ]
        await self._run(cmd)
        return output_path

    async def detect_black_frames(self, input_video: str) -> bool:
        cmd = [self.ffmpeg_bin, "-i", input_video, "-vf",
               "blackdetect=d=0.2:pix_th=0.10", "-an", "-f", "null", "-"]
        result = await self._run(cmd, capture_stderr=True, check=False)
        return "black_start" in result.get("stderr", "").lower()

    async def probe_duration(self, input_video: str) -> float:
        cmd = [self.ffprobe_bin, "-v", "quiet", "-print_format", "json",
               "-show_format", input_video]
        result = await self._run(cmd, capture_stdout=True)
        payload = json.loads(result["stdout"])
        return float(payload["format"]["duration"])

    # ─────────────────────────────────────────────────────────────
    # LEGACY API (VideoStitcher / FrameChainer)
    # ─────────────────────────────────────────────────────────────

    async def run_command(
        self, cmd: list[str], timeout: float = DEFAULT_TIMEOUT, cwd: Optional[str] = None,
    ) -> tuple[bool, str, str]:
        """Legacy: returns (success, stdout, stderr)."""
        logger.debug(f"Running: {' '.join(cmd[:6])}...")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return False, "", f"Command timed out after {timeout}s"

            stdout = stdout_b.decode("utf-8", errors="replace").strip()
            stderr = stderr_b.decode("utf-8", errors="replace").strip()
            return process.returncode == 0, stdout, stderr

        except FileNotFoundError:
            return False, "", f"{cmd[0]} not found. Install ffmpeg."
        except Exception as e:
            return False, "", str(e)

    async def get_duration(self, video_path: str) -> float:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", video_path]
        success, stdout, _ = await self.run_command(cmd, timeout=15)
        if not success or not stdout:
            return 0.0
        try:
            data = json.loads(stdout)
            dur = data.get("format", {}).get("duration")
            if dur:
                return float(dur)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    d = stream.get("duration")
                    if d:
                        return float(d)
        except Exception:
            pass
        return 0.0

    async def probe_video(self, video_path: str) -> dict:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", "-select_streams", "v:0", video_path]
        success, stdout, _ = await self.run_command(cmd, timeout=15)
        result = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0,
                  "video_codec": "", "audio_codec": "", "pix_fmt": "", "bit_rate": 0, "size_bytes": 0}
        if not success or not stdout:
            return result
        try:
            data = json.loads(stdout)
            fmt = data.get("format", {})
            result["duration"] = float(fmt.get("duration", 0))
            result["bit_rate"] = int(fmt.get("bit_rate", 0))
            result["size_bytes"] = int(fmt.get("size", 0))
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    result["video_codec"] = stream.get("codec_name", "")
                    result["width"] = stream.get("width", 0)
                    result["height"] = stream.get("height", 0)
                    result["pix_fmt"] = stream.get("pix_fmt", "")
                    fps_str = stream.get("r_frame_rate", "0/1")
                    try:
                        num, den = fps_str.split("/")
                        result["fps"] = float(num) / float(den)
                    except (ValueError, ZeroDivisionError):
                        result["fps"] = 0.0
                elif stream.get("codec_type") == "audio":
                    result["audio_codec"] = stream.get("codec_name", "")
        except Exception:
            pass
        return result

    async def extract_frame(
        self, video_path: str, timestamp: Optional[float] = None,
        from_end: bool = False, offset: float = 0.1,
        output_path: Optional[str] = None, quality: int = 2,
    ) -> Optional[str]:
        if not output_path:
            output_path = str(self.output_dir / f"frame_{int(time.time() * 1000)}.jpg")
        if from_end:
            cmd = ["ffmpeg", "-y", "-sseof", f"-{abs(offset)}", "-i", video_path,
                   "-frames:v", "1", "-q:v", str(quality), output_path]
        elif timestamp is not None:
            cmd = ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
                   "-frames:v", "1", "-q:v", str(quality), output_path]
        else:
            cmd = ["ffmpeg", "-y", "-i", video_path,
                   "-frames:v", "1", "-q:v", str(quality), output_path]
        success, _, stderr = await self.run_command(cmd, timeout=30)
        if success and Path(output_path).exists():
            return output_path
        logger.warning(f"Frame extraction failed: {stderr[:200]}")
        return None

    async def is_valid_video(self, video_path: str) -> bool:
        if not Path(video_path).exists():
            return False
        return await self.get_duration(video_path) > 0

    async def remux_to_mp4(self, input_path: str, output_path: Optional[str] = None) -> str:
        if not output_path:
            output_path = input_path.rsplit(".", 1)[0] + "_remuxed.mp4"
        cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", self.video_codec,
               "-preset", self.preset, "-crf", self.crf, "-pix_fmt", "yuv420p",
               "-c:a", self.audio_codec, "-b:a", "128k", "-movflags", "+faststart", output_path]
        success, _, stderr = await self.run_command(cmd, timeout=LONG_TIMEOUT)
        if not success:
            raise RuntimeError(f"Remux failed: {stderr[:300]}")
        return output_path

    @staticmethod
    def format_duration(seconds: float) -> str:
        secs = int(seconds)
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        h = secs // 3600
        return f"{h}h {(secs % 3600) // 60}m {secs % 60}s"

    # ─────────────────────────────────────────────────────────────
    # Internal async runner (used by Blueprint-style methods)
    # ─────────────────────────────────────────────────────────────

    async def _run(
        self,
        cmd: list[str],
        capture_stdout: bool = False,
        capture_stderr: bool = False,
        check: bool = True,
    ) -> dict:
        stdout_pipe = asyncio.subprocess.PIPE if capture_stdout else None
        stderr_pipe = asyncio.subprocess.PIPE

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=stdout_pipe, stderr=stderr_pipe,
        )
        stdout, stderr = await process.communicate()
        result = {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="ignore") if stdout else "",
            "stderr": stderr.decode("utf-8", errors="ignore") if stderr else "",
        }
        if self.logger:
            self.logger.info(
                "ffmpeg command executed",
                extra={"cmd": " ".join(cmd), "returncode": process.returncode},
            )
        if check and process.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result['stderr']}")
        return result
