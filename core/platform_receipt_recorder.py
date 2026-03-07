from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class PlatformReceiptRecorder:
    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "_publish_queue"
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "receipts.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.file.exists():
            return []
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(
        self,
        *,
        task_id: str,
        queue_id: str,
        platform: str,
        status: str,
        mode: str = "dry_run",
        attempt_id: str = "",
        remote_id: str = "",
        response: dict[str, Any] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        items = self._load()
        receipt = {
            "receipt_id": uuid.uuid4().hex,
            "task_id": task_id,
            "queue_id": queue_id,
            "platform": platform,
            "status": status,
            "mode": mode,
            "attempt_id": attempt_id,
            "remote_id": remote_id,
            "response": response or {},
            "note": note,
            "created_at": time.time(),
        }
        items.insert(0, receipt)
        self._save(items)
        return receipt

    def list(self, *, task_id: str | None = None, queue_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        items = self._load()
        if task_id:
            items = [x for x in items if x.get("task_id") == task_id]
        if queue_id:
            items = [x for x in items if x.get("queue_id") == queue_id]
        return items[:limit]
