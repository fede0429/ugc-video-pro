from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class PublishQueue:
    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "_publish_queue"
        self.root.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.root / "queue.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.queue_file.exists():
            return []
        try:
            return json.loads(self.queue_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.queue_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def enqueue(
        self,
        *,
        task_id: str,
        platform: str,
        payload: dict[str, Any],
        priority: str = "normal",
        scheduled_at: float | None = None,
        review_state: str = "draft",
    ) -> dict[str, Any]:
        items = self._load()
        is_scheduled = scheduled_at is not None
        entry = {
            "queue_id": uuid.uuid4().hex,
            "task_id": task_id,
            "platform": platform,
            "payload": payload,
            "priority": priority,
            "status": "scheduled" if is_scheduled else "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "scheduled_at": scheduled_at,
            "review_state": review_state,
            "retry_count": 0,
        }
        items.insert(0, entry)
        self._save(items)
        return entry

    def list(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        items = self._load()
        if status:
            items = [item for item in items if item.get("status") == status]
        return items[:limit]

    def list_due(self, now_ts: float | None = None, limit: int = 50) -> list[dict[str, Any]]:
        now_ts = now_ts or time.time()
        due = []
        for item in self._load():
            sched = item.get("scheduled_at")
            if item.get("status") in {"scheduled", "approved", "publish_ready"} and sched and float(sched) <= now_ts:
                due.append(item)
        return due[:limit]

    def update_status(self, queue_id: str, *, status: str, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
        items = self._load()
        found = None
        for item in items:
            if item.get("queue_id") == queue_id:
                item["status"] = status
                item["updated_at"] = time.time()
                if extra:
                    item.update(extra)
                found = item
                break
        if found:
            self._save(items)
        return found

    def get(self, queue_id: str) -> dict[str, Any] | None:
        for item in self._load():
            if item.get("queue_id") == queue_id:
                return item
        return None

    def reschedule(self, queue_id: str, scheduled_at: float, note: str = "") -> dict[str, Any] | None:
        return self.update_status(
            queue_id,
            status="scheduled",
            extra={"scheduled_at": scheduled_at, "reschedule_note": note, "rescheduled_at": time.time()},
        )
