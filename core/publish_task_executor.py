from __future__ import annotations

import time
from typing import Any

from .direct_publish_skeleton import DirectPublishSkeleton
from .platform_credential_center import PlatformCredentialCenter
from .platform_resource_center import PlatformResourceCenter
from .platform_receipt_recorder import PlatformReceiptRecorder
from .publish_queue import PublishQueue
from .review_state_machine import ReviewStateMachine


class PublishTaskExecutor:
    """
    Provider-ready direct publish executor skeleton.
    It prepares an execution envelope, validates review/credential prerequisites,
    writes queue status transitions, and records a platform receipt.
    """
    def __init__(self, config: dict):
        self.config = config
        self.queue = PublishQueue(config)
        self.credentials = PlatformCredentialCenter(config)
        self.resources = PlatformResourceCenter(config)
        self.receipts = PlatformReceiptRecorder(config)
        self.direct = DirectPublishSkeleton()
        self.review = ReviewStateMachine()

    def execute(self, queue_id: str, *, dry_run: bool = True, actor: str = "system", force: bool = False) -> dict[str, Any]:
        entry = self.queue.get(queue_id)
        if not entry:
            raise FileNotFoundError(f"Queue entry not found: {queue_id}")

        review_state = (entry.get("review_state") or "draft").lower()
        if not force and review_state not in {"approved", "publish_ready", "published"}:
            raise ValueError(f"Queue entry not publishable from review state: {review_state}")

        platform = (entry.get("platform") or "douyin").lower()
        auth_context = self.credentials.build_publish_auth_context(platform)
        if not force and not auth_context.get("has_credentials"):
            raise ValueError(f"Missing platform credentials for {platform}")

        payload = dict(entry.get("payload") or {})
        resource_bundle = self.resources.get_platform(platform)
        prepared = self.direct.build_attempt(
            task_id=entry.get("task_id") or "",
            platform=platform,
            publish_payload={
                **payload,
                "platform_resource_bundle": resource_bundle,
                "auth_context": auth_context,
                "queue_context": {
                    "queue_id": queue_id,
                    "priority": entry.get("priority"),
                    "scheduled_at": entry.get("scheduled_at"),
                },
            },
            dry_run=dry_run,
        ).to_dict()

        status = "published_dry_run" if dry_run else "publish_submitted"
        updated = self.queue.update_status(
            queue_id,
            status=status,
            extra={
                "last_executed_at": time.time(),
                "last_attempt": prepared,
                "last_executor": actor,
                "credential_ready": auth_context.get("ready", False),
            },
        ) or entry

        receipt = self.receipts.record(
            task_id=entry.get("task_id") or "",
            queue_id=queue_id,
            platform=platform,
            status=status,
            mode="dry_run" if dry_run else "submit",
            attempt_id=prepared.get("attempt_id", ""),
            remote_id=f"{platform}_sim_{queue_id[:8]}",
            response=prepared.get("response", {}),
            note="skeleton execution only; connect provider upload API next",
        )
        return {
            "queue_entry": updated,
            "attempt": prepared,
            "receipt": receipt,
            "auth_context": auth_context,
        }
