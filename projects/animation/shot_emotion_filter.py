from __future__ import annotations

from typing import Any


class ShotEmotionFilter:
    FILTER_MAP = {
        "压抑": {"filter": "cool desaturated, lower contrast", "camera_texture": "locked frame with subtle breathing"},
        "试探": {"filter": "neutral moody teal", "camera_texture": "micro push and hesitation cut"},
        "升温": {"filter": "warmer mids, selective highlight bloom", "camera_texture": "faster reaction cuts"},
        "失控": {"filter": "high contrast hot highlights", "camera_texture": "snap zoom + unstable handheld"},
        "反击": {"filter": "sharp contrast with cool shadows", "camera_texture": "assertive push-in"},
        "悬置": {"filter": "muted highlights, suspense shadows", "camera_texture": "hold on expression then cut"},
        "冷静": {"filter": "clean neutral cinematic", "camera_texture": "controlled framing"},
    }

    def build(self, episode: dict[str, Any], emotion_arcs: dict[str, Any]) -> dict[str, Any]:
        arc_map = emotion_arcs.get("emotion_arcs", {})
        filters = []
        for scene in episode.get("scenes", []):
            scene_id = scene.get("scene_id")
            scene_filters = []
            for name, info in arc_map.items():
                beat = next((b for b in info.get("scene_beats", []) if b.get("scene_id") == scene_id), None)
                if not beat:
                    continue
                emo = beat.get("emotion", "冷静")
                profile = self.FILTER_MAP.get(emo, self.FILTER_MAP["冷静"])
                scene_filters.append({
                    "character": name,
                    "emotion": emo,
                    "intensity": beat.get("intensity", 50),
                    "filter": profile["filter"],
                    "camera_texture": profile["camera_texture"],
                })
            dominant = max(scene_filters, key=lambda x: x.get("intensity", 0), default={"emotion": "冷静", "filter": self.FILTER_MAP["冷静"]["filter"], "camera_texture": self.FILTER_MAP["冷静"]["camera_texture"]})
            filters.append({
                "scene_id": scene_id,
                "dominant_emotion": dominant.get("emotion"),
                "dominant_filter": dominant.get("filter"),
                "camera_texture": dominant.get("camera_texture"),
                "scene_filters": scene_filters,
            })
        return {"shot_emotion_filters": filters}

    def apply_to_episode(self, episode, payload: dict[str, Any]):
        scene_map = {item.get("scene_id"): item for item in payload.get("shot_emotion_filters", [])}
        for scene in getattr(episode, "scenes", []) or []:
            item = scene_map.get(getattr(scene, "scene_id", ""))
            if not item:
                continue
            for shot in getattr(scene, "shots", []) or []:
                note = f"镜头情绪滤镜：{item.get('dominant_emotion')} | {item.get('dominant_filter')} | {item.get('camera_texture')}"
                shot.continuity_notes.append(note)
                try:
                    setattr(shot, "emotion_filter", item)
                except Exception:
                    pass
        return episode
