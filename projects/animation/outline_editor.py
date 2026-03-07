from __future__ import annotations

from typing import Any


class OutlineEditor:
    def build(self, title: str, premise: str, episode_goal: str, scene_count: int = 4, previous_memory: dict | None = None) -> dict[str, Any]:
        base_beats = [
            "开场钩子：抛出冲突或秘密",
            "第一次碰撞：角色目标正面冲突",
            "局势升级：引入阻碍、误会或压力",
            "结尾悬念：留下下一集必须解决的问题",
        ]
        beats = []
        for idx in range(scene_count):
            label = base_beats[min(idx, len(base_beats)-1)]
            beats.append({
                "scene_index": idx + 1,
                "beat_title": f"Scene {idx+1}",
                "beat_goal": label,
                "conflict_driver": episode_goal,
                "continuity_anchor": (previous_memory or {}).get("open_loops", ["关系还未稳定"])[0] if previous_memory else "延续人物关系线",
            })
        return {
            "title": title,
            "premise": premise,
            "episode_goal": episode_goal,
            "scene_count": scene_count,
            "beats": beats,
            "editor_notes": [
                "优先保证单集冲突完整，不要一上来塞太多世界观说明。",
                "每场戏都至少推动关系、秘密或目标中的一项。",
            ],
        }

    def revise(self, outline: dict[str, Any], change_request: str) -> dict[str, Any]:
        revised = dict(outline)
        revised.setdefault("revision_history", []).append({
            "change_request": change_request,
            "applied": True,
        })
        for beat in revised.get("beats", []):
            beat["editor_adjustment"] = change_request
        return revised
