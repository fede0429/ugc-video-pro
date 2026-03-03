"""
utils/ffmpeg_tools.py
=====================
FFmpeg wrappers and utilities for UGC Video Pro.

Provides async wrappers around ffmpeg and ffprobe:
    - run_command(): Run ffmpeg command asynchronously
    - get_duration(): Get video duration in seconds
    - probe_video(): Get video metadata (codec, resolution, fps)
    - extract_frame(): Extract a single frame from a video
    - is_valid_video(): Quick validity check
    - remux_to_mp4(): Re-encode to MP4
"""

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
    """Async wrapper around ffmpeg and ffprobe commands."""

    def __init__(self, config: dict):
        self.config = config
        video_config = config.get("video", {})
        self.output_dir = Path(video_config.get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.video_codec = video_config.get("video_codec", "libx264")
        self.audio_codec = video_config.get("audio_codec", "aac")
        self.crf = str(video_config.get("crf", 23))
        self.preset = video_config.get("preset", "fast")

    async def run_command(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_TIMEOUT,
        cwd: Optional[str] = None,
    ) -> tuple[bool, str, str]:
        """
        Run an ffmpeg/ffprobe command asynchronously.
        
        Returns:
            Tuple of (success: bool, stdout: str, stderr: str)
        """
        logger.debug(f"Running command: {' '.join(cmd[:6])}...")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                logger.error(f"Command timed out after {timeout}s: {cmd[0]}")
                return False, "", f"Command timed out after {timeout}s"

            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            success = process.returncode == 0

            if not success:
                logger.debug(
                    f"Command failed (code {process.returncode}): "
                    f"{stderr[-500:] if stderr else 'no stderr'}"
                )

            return success, stdout, stderr

        except FileNotFoundError:
            logger.error(f"Command not found: {cmd[0]}. Install ffmpeg.")
            return False, "", f"{cmd[0]} not found. Install ffmpeg."
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False, "", str(e)

    async def get_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]

        success, stdout, stderr = await self.run_command(cmd, timeout=15)

        if not success or not stdout:
            logger.warning(f"Could not probe duration of {video_path}")
            return 0.0

        try:
            data = json.loads(stdout)
            duration = data.get("format", {}).get("duration")
            if duration:
                return float(duration)

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    dur = stream.get("duration")
                    if dur:
                        return float(dur)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Duration parse error: {e}")

        return 0.0

    async def probe_video(self, video_path: str) -> dict:
        """Get comprehensive video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            "-select_streams", "v:0",
            video_path,
        ]

        success, stdout, stderr = await self.run_command(cmd, timeout=15)

        result = {
            "duration": 0.0, "width": 0, "height": 0, "fps": 0.0,
            "video_codec": "", "audio_codec": "", "pix_fmt": "",
            "bit_rate": 0, "size_bytes": 0,
        }

        if not success or not stdout:
            return result

        try:
            data = json.loads(stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])

            result["duration"] = float(fmt.get("duration", 0))
            result["bit_rate"] = int(fmt.get("bit_rate", 0))
            result["size_bytes"] = int(fmt.get("size", 0))

            for stream in streams:
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

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Video probe parse error: {e}")

        return result

    async def extract_frame(
        self,
        video_path: str,
        timestamp: Optional[float] = None,
        from_end: bool = False,
        offset: float = 0.1,
        output_path: Optional[str] = None,
        quality: int = 2,
    ) -> Optional[str]:
        """Extract a single frame from a video as JPEG."""
        if not output_path:
            output_path = str(
                self.output_dir / f"frame_{int(time.time() * 1000)}.jpg"
            )

        if from_end:
            cmd = [
                "ffmpeg", "-y",
                "-sseof", f"-{abs(offset)}",
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", str(quality),
                output_path,
            ]
        elif timestamp is not None:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", str(quality),
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", str(quality),
                output_path,
            ]

        success, stdout, stderr = await self.run_command(cmd, timeout=30)

        if success and Path(output_path).exists():
            return output_path
        else:
            logger.warning(f"Frame extraction failed: {stderr[:200]}")
            return None

    async def is_valid_video(self, video_path: str) -> bool:
        """Quick check if a file is a valid, readable video."""
        if not Path(video_path).exists():
            return False

        duration = await self.get_duration(video_path)
        return duration > 0

    async def remux_to_mp4(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Remux/re-encode a video to ensure MP4 compatibility."""
        if not output_path:
            output_path = input_path.rsplit(".", 1)[0] + "_remuxed.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", self.video_codec,
            "-preset", self.preset,
            "-crf", self.crf,
            "-pix_fmt", "yuv420p",
            "-c:a", self.audio_codec,
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

        success, stdout, stderr = await self.run_command(cmd, timeout=LONG_TIMEOUT)

        if not success:
            raise RuntimeError(f"Remux failed: {stderr[:300]}")

        return output_path

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        secs = int(seconds)
        if secs < 60:
            return f"{secs}s"
        elif secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        else:
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            return f"{h}h {m}m {s}s"
