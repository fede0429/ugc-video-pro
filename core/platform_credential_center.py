from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class PlatformCredentialCenter:
    DEFAULTS: dict[str, dict[str, Any]] = {
        "douyin": {"client_id": "", "client_secret": "", "access_token": "", "refresh_token": "", "account_label": ""},
        "xiaohongshu": {"client_id": "", "client_secret": "", "access_token": "", "refresh_token": "", "account_label": ""},
        "tiktok": {"client_id": "", "client_secret": "", "access_token": "", "refresh_token": "", "account_label": ""},
        "youtube": {"client_id": "", "client_secret": "", "access_token": "", "refresh_token": "", "channel_id": "", "account_label": ""},
    }

    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "_platform_credentials"
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "credentials.json"

    def _load(self) -> dict[str, Any]:
        if not self.file.exists():
            return {"updated_at": time.time(), "platforms": dict(self.DEFAULTS)}
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            data.setdefault("platforms", {})
            for name, defaults in self.DEFAULTS.items():
                data["platforms"].setdefault(name, dict(defaults))
            return data
        except Exception:
            return {"updated_at": time.time(), "platforms": dict(self.DEFAULTS)}

    def _save(self, data: dict[str, Any]) -> None:
        data["updated_at"] = time.time()
        self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _mask_value(key: str, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if key not in {"client_secret", "access_token", "refresh_token"}:
            return value
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}***{value[-4:]}"

    def get_all(self, masked: bool = True) -> dict[str, Any]:
        data = self._load()
        if not masked:
            return data
        masked_data = {"updated_at": data.get("updated_at"), "platforms": {}}
        for platform, creds in data.get("platforms", {}).items():
            masked_data["platforms"][platform] = {k: self._mask_value(k, v) for k, v in creds.items()}
        return masked_data

    def get_platform(self, platform: str, masked: bool = True) -> dict[str, Any]:
        platform = (platform or "").lower()
        creds = self._load().get("platforms", {}).get(platform, dict(self.DEFAULTS.get(platform, {})))
        if not masked:
            return creds
        return {k: self._mask_value(k, v) for k, v in creds.items()}

    def update_platform(self, platform: str, payload: dict[str, Any]) -> dict[str, Any]:
        platform = (platform or "").lower()
        data = self._load()
        merged = dict(self.DEFAULTS.get(platform, {}))
        merged.update(data.get("platforms", {}).get(platform, {}))
        merged.update(payload or {})
        data["platforms"][platform] = merged
        self._save(data)
        return self.get_platform(platform, masked=True)

    def has_ready_credentials(self, platform: str) -> bool:
        creds = self.get_platform(platform, masked=False)
        token = creds.get("access_token") or creds.get("refresh_token")
        return bool((creds.get("client_id") or token) and (creds.get("client_secret") or token))

    def build_publish_auth_context(self, platform: str) -> dict[str, Any]:
        creds = self.get_platform(platform, masked=False)
        return {
            "platform": platform,
            "has_credentials": self.has_ready_credentials(platform),
            "account_label": creds.get("account_label") or creds.get("channel_id") or "",
            "credential_fields": sorted(list(creds.keys())),
        }
