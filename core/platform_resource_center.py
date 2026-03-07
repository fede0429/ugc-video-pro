from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

class PlatformResourceCenter:
    DEFAULTS: dict[str, Any] = {
        "douyin": {
            "default_hashtags": ["#种草", "#好物推荐"],
            "cover_style_notes": ["大字封面", "前3秒强钩子", "突出利益点"],
            "credential_placeholder": {"client_id": "", "client_secret": "", "access_token": ""},
        },
        "xiaohongshu": {
            "default_hashtags": ["#真实测评", "#日常分享"],
            "cover_style_notes": ["生活化封面", "标题尽量口语化", "强调体验感"],
            "credential_placeholder": {"client_id": "", "client_secret": "", "access_token": ""},
        },
        "tiktok": {
            "default_hashtags": ["#fyp", "#ugccreator"],
            "cover_style_notes": ["quick hook", "human face first", "simple text"],
            "credential_placeholder": {"client_id": "", "client_secret": "", "access_token": ""},
        },
        "youtube": {
            "default_hashtags": ["#shorts", "#review"],
            "cover_style_notes": ["thumbnail contrast", "single promise headline"],
            "credential_placeholder": {"client_id": "", "client_secret": "", "refresh_token": ""},
        },
    }

    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "_platform_resources"
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "resources.json"
        if not self.file.exists():
            self._save({"platforms": self.DEFAULTS, "updated_at": time.time()})

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return {"platforms": self.DEFAULTS, "updated_at": time.time()}

    def _save(self, payload: dict[str, Any]) -> None:
        self.file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_all(self) -> dict[str, Any]:
        return self._load()

    def get_platform(self, platform: str) -> dict[str, Any]:
        payload = self._load()
        return payload.get("platforms", {}).get(platform, {})

    def update_platform(self, platform: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        platforms = dict(payload.get("platforms", {}))
        current = dict(platforms.get(platform, self.DEFAULTS.get(platform, {})))
        current.update(data or {})
        platforms[platform] = current
        payload["platforms"] = platforms
        payload["updated_at"] = time.time()
        self._save(payload)
        return current

    def build_resource_bundle(self, platform: str, publish_package: dict[str, Any] | None = None) -> dict[str, Any]:
        pack = dict(self.get_platform(platform) or {})
        publish_package = publish_package or {}
        merged_tags = list(dict.fromkeys((publish_package.get("hashtags") or []) + (pack.get("default_hashtags") or [])))[:12]
        return {
            "platform": platform,
            "default_hashtags": merged_tags,
            "cover_style_notes": pack.get("cover_style_notes", []),
            "credential_placeholder": pack.get("credential_placeholder", {}),
            "publishing_notes": publish_package.get("platform_notes", {}),
            "title_hint": publish_package.get("title") or publish_package.get("short_title") or "",
            "hook_line": publish_package.get("hook_line") or "",
        }
