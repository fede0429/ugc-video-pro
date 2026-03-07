from __future__ import annotations

import time
from typing import Any

from .direct_publish_skeleton import DirectPublishSkeleton
from .publish_queue import PublishQueue

class PublishRetryEngine:
    def __init__(self, config: dict):
        self.queue = PublishQueue(config)
        self.skeleton = DirectPublishSkeleton()

    def retry(self, queue_id: str, *, dry_run: bool = True, note: str = "") -> dict[str, Any]:
        entry = self.queue.get(queue_id)
        if not entry:
            raise FileNotFoundError(f"Queue entry not found: {queue_id}")
        payload = dict(entry.get("payload") or {})
        platform = entry.get("platform") or payload.get("platform") or "douyin"
        task_id = entry.get("task_id") or ""
        attempt = self.skeleton.build_attempt(
            task_id=task_id,
            platform=platform,
            publish_payload=payload,
            dry_run=dry_run,
        ).to_dict()
        retries = int(entry.get("retry_count") or 0) + 1
        updated = self.queue.update_status(
            queue_id,
            status="retry_prepared" if dry_run else "retry_pending_remote",
            extra={
                "retry_count": retries,
                "last_retry_at": time.time(),
                "last_retry_note": note,
                "last_retry_attempt": attempt,
            },
        )
        return {"queue": updated, "attempt": attempt}
