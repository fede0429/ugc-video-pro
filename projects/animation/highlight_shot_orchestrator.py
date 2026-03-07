from __future__ import annotations

from typing import Any


class HighlightShotOrchestrator:
    def build(self, episode: dict[str, Any], twist_report: dict[str, Any], climax_plan: dict[str, Any]) -> dict[str, Any]:
        scenes = episode.get("scenes", []) or []
        twist_ids = {item.get("scene_id") for item in twist_report.get("twist_scenes", [])}
        climax_id = (climax_plan.get("primary_climax_scene") or {}).get("scene_id")
        highlight_shots = []
        for scene in scenes:
            is_peak = scene.get("scene_id") in twist_ids or scene.get("scene_id") == climax_id
            if not is_peak:
                continue
            shots = scene.get("shots", []) or []
            if not shots:
                continue
            hero = shots[-1]
            highlight_shots.append({
                "scene_id": scene.get("scene_id"),
                "shot_id": hero.get("shot_id"),
                "recipe": [
                    "reaction close-up",
                    "insert prop detail" if any("道具" in b or "证据" in b for b in scene.get("beats", [])) else "micro pause",
                    "subtitle punch emphasis",
                ],
                "camera_push": "slow push-in" if scene.get("scene_id") == climax_id else "snap zoom",
                "subtitle_strategy": "single-line emphasis",
                "reason": scene.get("dramatic_purpose"),
            })
        return {
            "highlight_shots": highlight_shots,
            "hero_highlight": highlight_shots[0] if highlight_shots else None,
            "editing_notes": [
                "高潮前 1.0~1.5 秒保留呼吸停顿",
                "反转信息前后用字幕节奏做对比",
                "爆点镜头优先保留人物反应而不是全景交代",
            ],
        }
