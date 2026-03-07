from __future__ import annotations

from typing import Any


class ForeshadowPlanter:
    """
    Plants pre-twist cues before the strongest twist/climax scene so later renders
    can keep clue continuity and editorial payoff.
    """
    def build(self, episode: dict[str, Any], twist_report: dict[str, Any], relationship_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        relationship_graph = relationship_graph or {}
        strongest = twist_report.get("strongest_twist") or {}
        target_scene = strongest.get("scene_id")
        seeds = []
        scenes = episode.get("scenes", []) or []
        edges = relationship_graph.get("edges", []) or []
        for idx, scene in enumerate(scenes):
            if scene.get("scene_id") == target_scene:
                break
            clue = {
                "scene_id": scene.get("scene_id"),
                "seed_type": "prop_clue" if idx % 2 == 0 else "dialogue_glitch",
                "foreshadow_line": f"在{scene.get('title', '本场')}里埋下一个看似无关、实则指向后续反转的细节。",
                "payoff_target": target_scene,
                "editorial_hint": "不要正面解释，只给半秒信息或一句话错位回应。",
                "relationship_hint": edges[idx % len(edges)].get("dynamic_summary", "") if edges else "",
            }
            seeds.append(clue)
        return {"target_twist_scene": target_scene, "foreshadow_seeds": seeds}

    def apply_to_episode(self, episode, payload: dict[str, Any]):
        seed_map = {item.get("scene_id"): item for item in payload.get("foreshadow_seeds", [])}
        for scene in getattr(episode, "scenes", []) or []:
            item = seed_map.get(getattr(scene, "scene_id", ""))
            if not item:
                continue
            shots = getattr(scene, "shots", []) or []
            if not shots:
                continue
            target = shots[0]
            target.continuity_notes.append(
                f"反转前埋点：{item.get('seed_type')} -> {item.get('foreshadow_line')} | payoff={item.get('payoff_target')}"
            )
            try:
                setattr(target, "foreshadow_seed", item)
            except Exception:
                pass
        return episode
