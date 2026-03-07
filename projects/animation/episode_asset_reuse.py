from __future__ import annotations

import hashlib
from pathlib import Path
import json


class EpisodeAssetReusePlanner:
    def __init__(self, store=None):
        self.store = store

    def build(self, story_bible, characters, episode, scene_assets: dict | None = None, batch_parent_id: str | None = None) -> dict:
        character_keys = {
            c.name: self._key(story_bible.title, c.name, ",".join(c.appearance[:3]), ",".join(c.wardrobe[:2]))
            for c in characters
        }
        scene_keys = {
            scene.scene_id: self._key(story_bible.title, scene.location, scene.dramatic_purpose)
            for scene in episode.scenes
        }
        reusable_assets = []
        for c in characters:
            reusable_assets.append({
                "asset_group": "character_anchor",
                "name": c.name,
                "cache_key": character_keys[c.name],
                "reference_image_url": c.reference_image_url,
                "reusable_across_episodes": True,
            })
        for scene in episode.scenes:
            reusable_assets.append({
                "asset_group": "scene_anchor",
                "name": scene.location,
                "cache_key": scene_keys[scene.scene_id],
                "reusable_across_episodes": True,
            })
        inherited_assets = self._load_batch_cache(batch_parent_id) if batch_parent_id else []
        return {
            "batch_parent_id": batch_parent_id,
            "character_cache_keys": character_keys,
            "scene_cache_keys": scene_keys,
            "reusable_assets": reusable_assets,
            "inherited_assets": inherited_assets,
            "reuse_strategy": "prefer_previous_episode_assets_then_scene_library",
        }

    def update_batch_cache(self, batch_parent_id: str | None, episode_title: str, reuse_plan: dict) -> None:
        if not batch_parent_id or not self.store:
            return
        cache_path = self.store.batch_cache_path(batch_parent_id)
        cache = {"episodes": []}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                cache = {"episodes": []}
        cache["episodes"].append({
            "episode_title": episode_title,
            "reusable_assets": reuse_plan.get("reusable_assets", []),
        })
        cache["reusable_assets"] = self._dedupe([asset for ep in cache["episodes"] for asset in ep.get("reusable_assets", [])])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_batch_cache(self, batch_parent_id: str) -> list[dict]:
        if not self.store:
            return []
        path = self.store.batch_cache_path(batch_parent_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("reusable_assets", [])
        except Exception:
            return []

    def _dedupe(self, assets: list[dict]) -> list[dict]:
        seen = set()
        out = []
        for asset in assets:
            key = (asset.get("asset_group"), asset.get("cache_key"))
            if key in seen:
                continue
            seen.add(key)
            out.append(asset)
        return out

    def _key(self, *parts: str) -> str:
        joined = "|".join(str(p or "") for p in parts)
        return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]
