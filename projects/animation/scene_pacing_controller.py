
from __future__ import annotations

from typing import Any


class ScenePacingController:
    PURPOSE_DURATIONS = {
        "hook": 2.5,
        "setup": 4.0,
        "conflict": 4.5,
        "reveal": 3.5,
        "climax": 5.0,
        "aftermath": 3.0,
    }

    def build(self, episode: dict[str, Any]) -> dict[str, Any]:
        scenes = episode.get("scenes", [])
        scene_pacing = []
        total_duration = 0.0
        for idx, scene in enumerate(scenes):
            purpose = (scene.get("dramatic_purpose") or "setup").lower()
            beats = scene.get("beats") or []
            base = self.PURPOSE_DURATIONS.get(purpose, 4.0)
            duration = round(base + min(len(beats), 4) * 0.6, 1)
            scene_pacing.append({
                "scene_id": scene.get("scene_id", f"scene_{idx+1}"),
                "purpose": purpose,
                "recommended_duration_seconds": duration,
                "energy_curve": "high" if purpose in {"hook", "conflict", "climax"} else "mid",
                "shot_density": 4 if purpose == "climax" else 3 if purpose in {"conflict", "reveal"} else 2,
            })
            total_duration += duration
        return {
            "total_recommended_duration_seconds": round(total_duration, 1),
            "scene_pacing": scene_pacing,
            "notes": ["压缩铺垫，拉高冲突段镜头密度", "高潮段优先快切与特写交替"],
        }
