from __future__ import annotations

from typing import Any


class SceneTwistDetector:
    KEYWORDS = [
        ("身份暴露", ["真相", "身份", "揭穿", "暴露"]),
        ("立场反转", ["背叛", "改口", "反站队", "倒戈"]),
        ("情感逆转", ["原谅", "误会", "表白", "心软"]),
        ("利益反转", ["遗嘱", "合同", "股权", "录音"]),
    ]

    def build(self, episode: dict[str, Any]) -> dict[str, Any]:
        scenes = episode.get("scenes", []) or []
        twist_scenes = []
        strongest = None
        for idx, scene in enumerate(scenes, start=1):
            joined = " ".join(scene.get("beats", []) + scene.get("dialogue_summary", []) + [scene.get("dramatic_purpose", "")])
            labels = []
            score = 45
            for label, words in self.KEYWORDS:
                if any(w in joined for w in words):
                    labels.append(label)
                    score += 12
            if idx >= max(2, len(scenes) - 1):
                score += 8
            item = {
                "scene_id": scene.get("scene_id"),
                "title": scene.get("title"),
                "twist_score": min(100, score),
                "twist_labels": labels or ["冲突升级"],
                "twist_reason": joined[:180],
                "recommended_reveal_mode": "reaction_cut + insert close-up" if score >= 70 else "hold tension + slow reveal",
            }
            if item["twist_score"] >= 60:
                twist_scenes.append(item)
            if strongest is None or item["twist_score"] > strongest["twist_score"]:
                strongest = item
        return {
            "twist_scenes": twist_scenes,
            "strongest_twist": strongest,
            "recommended_twist_window": strongest.get("scene_id") if strongest else None,
        }
