
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .models import AnimationTaskState


class AnimationTaskStore:
    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "animation_tasks"
        self.assets_root = self.root / "_assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets_root.mkdir(parents=True, exist_ok=True)

    def create(self, initial: dict | None = None) -> AnimationTaskState:
        task_id = uuid.uuid4().hex
        task_dir = self.root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        state = AnimationTaskState(
            task_id=task_id,
            status="pending",
            stage="queued",
            stage_message="任务已创建",
            progress=0,
            task_dir=str(task_dir),
            artifacts={},
            plan=None,
            shot_results=[],
            batch_children=[],
        )
        if initial:
            for k, v in initial.items():
                if hasattr(state, k):
                    setattr(state, k, v)
        self.save(state)
        return state

    def path(self, task_id: str) -> Path:
        return self.root / task_id

    def file(self, task_id: str) -> Path:
        return self.path(task_id) / "task.json"

    def save(self, state: AnimationTaskState | dict[str, Any]) -> None:
        payload = state.to_dict() if hasattr(state, "to_dict") else dict(state)
        task_id = payload["task_id"]
        p = self.file(task_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload.setdefault("updated_at", time.time())
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def load(self, task_id: str) -> dict[str, Any] | None:
        p = self.file(task_id)
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def update(self, task_id: str, **fields) -> dict[str, Any]:
        state = self.load(task_id) or {"task_id": task_id, "artifacts": {}, "shot_results": [], "batch_children": []}
        if "artifacts" in fields and isinstance(fields["artifacts"], dict):
            merged = dict(state.get("artifacts", {}))
            merged.update(fields["artifacts"])
            fields["artifacts"] = merged
        if "shot_results" in fields and fields["shot_results"] is None:
            fields["shot_results"] = state.get("shot_results", [])
        state.update(fields)
        state["updated_at"] = time.time()
        self.save(state)
        return state

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        items = []
        for task_file in self.root.glob("*/task.json"):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                items.append(payload)
            except Exception:
                continue
        items.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
        return items[:limit]

    def mark_timestamp(self, task_id: str) -> None:
        state = self.load(task_id) or {"task_id": task_id}
        state["updated_at"] = time.time()
        self.save(state)

    def save_reference_asset(self, character_name: str, filename: str, content: bytes) -> dict[str, str]:
        ext = Path(filename).suffix or ".png"
        asset_id = uuid.uuid4().hex
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in character_name)[:40] or "character"
        dest = self.assets_root / f"{safe_name}_{asset_id}{ext}"
        dest.write_bytes(content)
        return {
            "asset_id": asset_id,
            "character_name": character_name,
            "file_name": dest.name,
            "local_path": str(dest),
        }

    def get_asset_path(self, asset_id: str) -> Path | None:
        for p in self.assets_root.glob(f"*_{asset_id}.*"):
            return p
        return None

    def batch_cache_path(self, batch_parent_id: str) -> Path:
        batch_dir = self.root / "_batch_cache"
        batch_dir.mkdir(parents=True, exist_ok=True)
        return batch_dir / f"{batch_parent_id}.json"

    def batch_root(self) -> Path:
        root = self.root / "_batch_memory"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def save_batch_memory(self, batch_id: str, memory: dict) -> str:
        if not batch_id:
            batch_id = "default_batch"
        path = self.batch_root() / f"{batch_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
        return str(path)

    def load_batch_memory(self, batch_id: str) -> dict | None:
        if not batch_id:
            return None
        path = self.batch_root() / f"{batch_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)




def _season_root(self) -> Path:
    root = self.root / "_season_memory"
    root.mkdir(parents=True, exist_ok=True)
    return root

def _save_season_memory(self, season_id: str, memory: dict) -> str:
    season_id = season_id or "default_season"
    path = self.season_root() / f"{season_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    return str(path)

def _load_season_memory(self, season_id: str) -> dict | None:
    if not season_id:
        return None
    path = self.season_root() / f"{season_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

AnimationTaskStore.season_root = _season_root
AnimationTaskStore.save_season_memory = _save_season_memory
AnimationTaskStore.load_season_memory = _load_season_memory
