
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PlatformPublishPayload:
    platform: str
    title: str
    description: str
    hashtags: list[str] = field(default_factory=list)
    cover_text: str = ""
    caption: str = ""
    upload_strategy: dict[str, Any] = field(default_factory=dict)
    asset_bundle: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlatformPublishAdapter:
    PLATFORM_RULES: dict[str, dict[str, Any]] = {
        "douyin": {"title_limit": 20, "hashtags_limit": 8, "ratio": "9:16", "cta": "评论区/主页引导"},
        "xiaohongshu": {"title_limit": 22, "hashtags_limit": 10, "ratio": "3:4", "cta": "收藏+私信"},
        "tiktok": {"title_limit": 80, "hashtags_limit": 8, "ratio": "9:16", "cta": "link in bio"},
        "youtube": {"title_limit": 90, "hashtags_limit": 15, "ratio": "16:9", "cta": "description/pinned comment"},
    }

    def build_payload(
        self,
        *,
        platform: str,
        publish_package: dict[str, Any],
        final_video_path: str | None = None,
        subtitle_path: str | None = None,
        task_id: str | None = None,
    ) -> PlatformPublishPayload:
        platform = (platform or "douyin").lower()
        rules = self.PLATFORM_RULES.get(platform, self.PLATFORM_RULES["douyin"])
        title = (publish_package.get("short_title") or publish_package.get("title") or "UGC视频")[: rules["title_limit"]]
        desc = publish_package.get("description") or publish_package.get("title") or title
        hashtags = list(dict.fromkeys((publish_package.get("hashtags") or [])[: rules["hashtags_limit"]]))
        cover_text = (publish_package.get("platform_notes") or {}).get("recommended_cover_text", "") or publish_package.get("hook_line", "")
        caption = ""
        for option in publish_package.get("caption_options") or []:
            if option:
                caption = option
                break
        upload_strategy = {
            "preferred_ratio": rules["ratio"],
            "cta_mode": rules["cta"],
            "title_limit": rules["title_limit"],
            "manual_review_required": True,
            "task_id": task_id or "",
        }
        asset_bundle = []
        if final_video_path:
            asset_bundle.append({"asset_type": "final_video", "path": final_video_path})
        if subtitle_path:
            asset_bundle.append({"asset_type": "subtitle", "path": subtitle_path})
        asset_bundle.extend(publish_package.get("reusable_assets") or [])
        return PlatformPublishPayload(
            platform=platform,
            title=title,
            description=desc,
            hashtags=hashtags,
            cover_text=cover_text[:24],
            caption=caption[:220],
            upload_strategy=upload_strategy,
            asset_bundle=asset_bundle[:20],
        )
