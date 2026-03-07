
from __future__ import annotations

class SuspenseKeeper:
    def build(self, episode: dict, scene_twists: dict | None = None, foreshadow_plan: dict | None = None, climax_plan: dict | None = None) -> dict:
        scenes = episode.get("scenes", [])
        twist_ids = {item.get("scene_id") for item in (scene_twists or {}).get("twist_scenes", [])}
        seeds = (foreshadow_plan or {}).get("foreshadow_seeds", [])
        climax_scene = (climax_plan or {}).get("primary_climax_scene")
        curve = []
        candidates = []
        for index, scene in enumerate(scenes, start=1):
            base = 52 + index * 4
            if scene.get("scene_id") in twist_ids:
                base += 10
            if climax_scene and scene.get("scene_id") == climax_scene:
                base += 12
            if any(seed.get("target_scene_id") == scene.get("scene_id") for seed in seeds):
                base += 7
            suspense_score = min(98, base)
            entry = {
                "scene_id": scene.get("scene_id"),
                "scene_title": scene.get("title"),
                "suspense_score": suspense_score,
                "retention_hint": "保留信息缺口，不提前解释因果；镜头停在角色反应后半拍。",
                "cliffhanger_ready": suspense_score >= 68,
            }
            curve.append(entry)
            if entry["cliffhanger_ready"]:
                candidates.append(entry)
        strongest = max(curve, key=lambda x: x["suspense_score"]) if curve else None
        mid_scene = scenes[max(0, len(scenes)//2 - 1)] if scenes else {}
        retention_windows = [
            {"window": "opening_3s", "focus": "抛出冲突但不解释"},
            {"window": "mid_hold", "focus": "给证据碎片，不给完整答案"},
            {"window": "pre_climax", "focus": "把反应和空镜留给观众补全"},
        ]
        suspense_index = round(sum(item["suspense_score"] for item in curve) / len(curve), 1) if curve else 0.0
        return {
            "suspense_curve": curve,
            "strongest_hold_scene": strongest,
            "recommended_mid_episode_hook": {
                "scene_id": mid_scene.get("scene_id"),
                "hook": "把最关键的信息只露一半，再切去角色反应。"
            } if mid_scene else None,
            "cliffhanger_candidates": candidates[:3],
            "retention_windows": retention_windows,
            "suspense_index": suspense_index,
        }

    def apply_to_episode(self, episode_obj, suspense: dict) -> None:
        strongest = (suspense or {}).get("strongest_hold_scene") or {}
        strongest_id = strongest.get("scene_id")
        cliffhanger_ids = {item.get("scene_id") for item in (suspense or {}).get("cliffhanger_candidates", [])}
        curve_map = {item.get("scene_id"): item for item in (suspense or {}).get("suspense_curve", [])}
        for scene in getattr(episode_obj, "scenes", []):
            scene_score = curve_map.get(scene.scene_id, {}).get("suspense_score")
            for shot in getattr(scene, "shots", []):
                if scene_score:
                    shot.continuity_notes.append(f"悬念强度：{scene_score}，不要提前泄露答案。")
                if scene.scene_id == strongest_id:
                    shot.continuity_notes.append("强悬念场：镜头优先保留停顿、遮挡和视线引导。")
                if scene.scene_id in cliffhanger_ids:
                    shot.continuity_notes.append("悬念候选场：结尾镜头保留空白，留给下场戏回收。")
