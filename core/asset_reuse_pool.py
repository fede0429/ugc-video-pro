from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class AssetReusePool:
    """Small local reuse pool for UGC outputs and source materials.

    Stores reusable clips, prompts, hooks, and publishing metadata by product key.
    """

    def __init__(self, config: dict):
        web_cfg = config.get("web", {})
        video_dir = Path(web_cfg.get("video_dir", "/app/data/videos"))
        self.root = video_dir / "ugc_asset_pool"
        self.root.mkdir(parents=True, exist_ok=True)

    def _product_key(self, request=None, product_profile=None) -> str:
        brand = getattr(product_profile, "brand", "") or ""
        desc = getattr(product_profile, "description", "") or ""
        if not brand and request is not None:
            brand = getattr(request, "brand_name", "") or getattr(request, "product_name", "") or ""
        key = f"{brand}_{desc}".strip("_").lower()
        key = "".join(ch if ch.isalnum() else "_" for ch in key)[:80]
        return key or "generic_product"

    def product_dir(self, request=None, product_profile=None, product_key: str | None = None) -> Path:
        key = product_key or self._product_key(request=request, product_profile=product_profile)
        p = self.root / key
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_entry(self, *, request=None, product_profile=None, payload: dict[str, Any]) -> dict[str, Any]:
        entry_id = uuid.uuid4().hex
        product_dir = self.product_dir(request=request, product_profile=product_profile)
        path = product_dir / f"{entry_id}.json"
        enriched = {
            "entry_id": entry_id,
            "product_key": product_dir.name,
            "created_at": time.time(),
            **payload,
        }
        path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
        return enriched

    def list_entries(self, *, request=None, product_profile=None, product_key: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        product_dir = self.product_dir(request=request, product_profile=product_profile, product_key=product_key)
        items: list[dict[str, Any]] = []
        for file in product_dir.glob("*.json"):
            try:
                items.append(json.loads(file.read_text(encoding="utf-8")))
            except Exception:
                continue
        items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return items[:limit]

    def summarize(self, *, request=None, product_profile=None, product_key: str | None = None) -> dict[str, Any]:
        items = self.list_entries(request=request, product_profile=product_profile, product_key=product_key, limit=50)
        hooks = []
        assets = []
        for item in items:
            hooks.extend(item.get("hook_lines", []))
            assets.extend(item.get("reusable_assets", []))
        return {
            "product_key": (product_key or self._product_key(request=request, product_profile=product_profile)),
            "entry_count": len(items),
            "recent_hooks": hooks[:10],
            "reusable_assets": assets[:20],
            "items": items[:10],
        }
