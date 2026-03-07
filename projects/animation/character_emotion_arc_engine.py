from __future__ import annotations

from typing import Any

class CharacterEmotionArcEngine:
    EMOTION_CURVE = ["压抑", "试探", "升温", "失控", "反击", "悬置"]

    def build(self, episode: dict[str, Any], characters: list[dict[str, Any]]) -> dict[str, Any]:
        scenes = episode.get("scenes", [])
        arcs = {}
        for idx, char in enumerate(characters):
            name = char.get("name", "")
            beats = []
            base = idx % 2
            for s_idx, scene in enumerate(scenes):
                emotion = self.EMOTION_CURVE[min(s_idx + base, len(self.EMOTION_CURVE) - 1)]
                beats.append({
                    "scene_id": scene.get("scene_id"),
                    "emotion": emotion,
                    "intensity": min(100, 35 + s_idx * 15 + idx * 5),
                    "trigger": scene.get("dramatic_purpose", ""),
                })
            arcs[name] = {
                "role": char.get("role", ""),
                "dominant_arc": "克制→失控→反击" if idx == 0 else "嘴硬→动摇→揭底",
                "scene_beats": beats,
            }
        return {"emotion_arcs": arcs, "global_curve": [s.get("dramatic_purpose","") for s in scenes]}

    def apply_to_episode(self, episode, emotion_arcs: dict[str, Any]):
        arc_map = emotion_arcs.get("emotion_arcs", {})
        scenes = getattr(episode, "scenes", []) or []
        for scene in scenes:
            for shot in getattr(scene, "shots", []) or []:
                hay = f"{getattr(shot, 'action', '')} {getattr(shot, 'dialogue', '')}"
                tags = []
                for name, info in arc_map.items():
                    if name and name in hay:
                        beat = next((b for b in info.get("scene_beats", []) if b.get("scene_id") == getattr(scene, "scene_id", "")), None)
                        if beat:
                            tags.append(f"{name}:{beat.get('emotion')}({beat.get('intensity')})")
                if tags:
                    shot.continuity_notes.append("情绪弧线锚点：" + " / ".join(tags))
                    try:
                        setattr(shot, "emotion_arc_tags", tags)
                    except Exception:
                        pass
        return episode
