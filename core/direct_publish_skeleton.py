
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DirectPublishAttempt:
    attempt_id: str
    platform: str
    task_id: str
    status: str
    mode: str = "skeleton"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DirectPublishSkeleton:
    """
    Real platform direct-publish skeleton.
    This does not post to external platforms yet; it normalizes payload and
    returns a provider-ready envelope for later adapter implementation.
    """

    PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
        "douyin": {"transport": "oauth_video_upload", "review_required": True},
        "xiaohongshu": {"transport": "manual_or_partner_api", "review_required": True},
        "tiktok": {"transport": "oauth_content_post", "review_required": True},
        "youtube": {"transport": "oauth_resumable_upload", "review_required": False},
    }

    def build_attempt(
        self,
        *,
        task_id: str,
        platform: str,
        publish_payload: dict[str, Any],
        dry_run: bool = True,
    ) -> DirectPublishAttempt:
        platform = (platform or "douyin").lower()
        profile = self.PLATFORM_PROFILES.get(platform, self.PLATFORM_PROFILES["douyin"])
        response = {
            "ready": True,
            "dry_run": dry_run,
            "provider": platform,
            "transport": profile["transport"],
            "review_required": profile["review_required"],
            "next_step": "connect real platform credentials and exchange upload token",
        }
        return DirectPublishAttempt(
            attempt_id=uuid.uuid4().hex,
            platform=platform,
            task_id=task_id,
            status="prepared" if dry_run else "pending_remote",
            payload={
                "profile": profile,
                "publish_payload": publish_payload,
            },
            response=response,
        )
