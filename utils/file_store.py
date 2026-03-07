"""
utils/file_store.py
===================
Unified file management for the UGC video production pipeline.

FileStore is the single authority for every on-disk path.
All modules receive a FileStore instance — no module hard-codes paths.

Directory tree per task:
    <base_dir>/tasks/<task_id>/
        inputs/
            product_primary/   ← primary product image(s)
            product_gallery/   ← detail / angle shots
            product_usage/     ← in-use / context images
            presenter_image/   ← face photo
            presenter_video/   ← reference video
        audio/                 ← TTS WAV per A-roll segment
        video/
            a_roll/            ← lipsync MP4 per A-roll segment
            b_roll/            ← AI-generated MP4 per B-roll segment
        subtitles/             ← captions.srt / captions.vtt
        reports/               ← timeline.json, product_profile.json, qa_report.json, ...
        final/                 ← final_video.mp4, final_voice.wav, cover.jpg
        temp/                  ← scratch files (cleared after completion)
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Union


class FileStore:
    """
    Manages on-disk file layout for all video production tasks.

    Two construction styles:
        FileStore("data")                      # new pipeline
        FileStore(config, task_id)             # legacy constructor shim
    """

    def __init__(self, base_dir_or_config, task_id: str | None = None):
        # Support legacy: FileStore(config_dict, task_id)
        if isinstance(base_dir_or_config, dict):
            config = base_dir_or_config
            ugc_config = config.get("ugc", {})
            base = ugc_config.get("data_root") or config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
            self.base_dir = Path(base)
        else:
            self.base_dir = Path(base_dir_or_config)

        self.uploads_dir = self.base_dir / "uploads"
        self.tasks_dir   = self.base_dir / "tasks"
        self.renders_dir = self.base_dir / "renders"
        self.temp_dir    = self.base_dir / "temp"
        self._ensure_base_dirs()

        # If task_id provided (legacy shim), pre-create dirs
        if task_id:
            self.create_task_dirs(task_id)

    def _ensure_base_dirs(self) -> None:
        for d in (self.uploads_dir, self.tasks_dir, self.renders_dir, self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── ID generation ─────────────────────────────────────────────────────────

    def new_task_id(self) -> str:
        return uuid.uuid4().hex

    # ── Directory management ──────────────────────────────────────────────────

    def task_root(self, task_id: str) -> Path:
        return self.tasks_dir / task_id

    # Alias for backward compat
    def task_dir(self, task_id: str) -> Path:
        return self.task_root(task_id)

    def create_task_dirs(self, task_id: str) -> Path:
        """Create the full directory tree for a new task."""
        root = self.task_root(task_id)
        subdirs = [
            "inputs/product_primary",
            "inputs/product_gallery",
            "inputs/product_usage",
            "inputs/presenter_image",
            "inputs/presenter_video",
            "audio",
            "video/a_roll",
            "video/b_roll",
            "subtitles",
            "reports",
            "final",
            "temp",
        ]
        for sub in subdirs:
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root

    def cleanup_task_temp(self, task_id: str) -> None:
        temp = self.task_root(task_id) / "temp"
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)

    def delete_task_dirs(self, task_id: str) -> None:
        d = self.task_root(task_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    # ── Async upload save ─────────────────────────────────────────────────────

    async def save_upload(self, task_id: str, upload_file, asset_group: str) -> str:
        """
        Save a FastAPI UploadFile to the task's inputs/<asset_group>/ directory.
        Returns the absolute path as a string.
        """
        dest_dir = self.task_root(task_id) / "inputs" / asset_group
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = upload_file.filename or f"{uuid.uuid4().hex}.bin"
        dest = dest_dir / filename
        content = await upload_file.read()
        dest.write_bytes(content)
        return str(dest)

    def save_bytes(self, task_id: str, asset_group: str, filename: str, data: bytes) -> str:
        """Synchronous save for raw bytes. Returns absolute path."""
        dest_dir = self.task_root(task_id) / "inputs" / asset_group
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        dest.write_bytes(data)
        return str(dest)

    # ── Audio ─────────────────────────────────────────────────────────────────

    def segment_audio_path(self, task_id: str, segment_id: str, ext: str = "wav") -> str:
        """Path for a single TTS audio segment."""
        path = self.task_root(task_id) / "audio" / f"{segment_id}.{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # Backward-compat alias
    def audio_path(self, task_id: str, segment_id: str, extension: str = "mp3") -> str:
        return self.segment_audio_path(task_id, segment_id, ext=extension)

    def final_audio_path(self, task_id: str) -> str:
        """Path for the merged full-voice track."""
        path = self.task_root(task_id) / "final" / "final_voice.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def all_audio_paths(self, task_id: str) -> list[str]:
        d = self.task_root(task_id) / "audio"
        if not d.exists():
            return []
        return sorted(str(p) for p in d.iterdir() if p.is_file())

    # ── Video segments ────────────────────────────────────────────────────────

    def segment_video_path(self, task_id: str, segment_id: str, track_type: str) -> str:
        """
        Path for a rendered video clip.
        track_type must be 'a_roll' or 'b_roll'.
        """
        if track_type not in {"a_roll", "b_roll"}:
            raise ValueError(f"unsupported track_type: {track_type!r}")
        path = self.task_root(task_id) / "video" / track_type / f"{segment_id}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # Backward-compat aliases
    def a_roll_path(self, task_id: str, segment_id: str) -> str:
        return self.segment_video_path(task_id, segment_id, "a_roll")

    def b_roll_path(self, task_id: str, segment_id: str) -> str:
        return self.segment_video_path(task_id, segment_id, "b_roll")

    # ── Subtitles ─────────────────────────────────────────────────────────────

    def subtitle_path(self, task_id: str, extension: str = "srt") -> str:
        path = self.task_root(task_id) / "subtitles" / f"captions.{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ── Frames (for frame-chaining legacy) ───────────────────────────────────

    def frame_path(self, task_id: str, segment_id: str) -> str:
        path = self.task_root(task_id) / "temp" / f"{segment_id}_last.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ── Final output ──────────────────────────────────────────────────────────

    def final_video_path(self, task_id: str, filename: str = "final_video.mp4") -> str:
        path = self.task_root(task_id) / "final" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def cover_path(self, task_id: str) -> str:
        path = self.task_root(task_id) / "final" / "cover.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ── JSON metadata ─────────────────────────────────────────────────────────

    def timeline_json_path(self, task_id: str) -> str:
        path = self.task_root(task_id) / "reports" / "timeline.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # Backward-compat alias
    def timeline_path(self, task_id: str) -> str:
        return self.timeline_json_path(task_id)

    def product_profile_path(self, task_id: str) -> str:
        path = self.task_root(task_id) / "reports" / "product_profile.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def presenter_profile_path(self, task_id: str) -> str:
        path = self.task_root(task_id) / "reports" / "presenter_profile.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def qa_report_path(self, task_id: str) -> str:
        path = self.task_root(task_id) / "reports" / "qa_report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ── Relative / absolute helpers (for DB storage) ─────────────────────────

    def relative(self, absolute_path: str) -> str:
        try:
            return str(Path(absolute_path).relative_to(self.base_dir))
        except ValueError:
            return absolute_path

    def absolute(self, relative_path: str) -> str:
        return str(self.base_dir / relative_path)
