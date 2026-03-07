
from __future__ import annotations

from typing import Any


class ClimaxOrchestrator:
    def build(self, episode: dict[str, Any], relationship_graph: dict[str, Any] | None = None, season_conflict_tree: dict[str, Any] | None = None) -> dict[str, Any]:
        scenes = episode.get("scenes", [])
        climax_candidates = []
        for idx, scene in enumerate(scenes):
            purpose = (scene.get("dramatic_purpose") or "").lower()
            score = 0
            if purpose in {"conflict", "reveal", "climax"}:
                score += 50
            score += min(len(scene.get("beats") or []), 4) * 10
            if idx == len(scenes) - 1:
                score += 10
            climax_candidates.append({
                "scene_id": scene.get("scene_id", f"scene_{idx+1}"),
                "score": score,
                "reason": f"purpose={purpose}, beats={len(scene.get('beats') or [])}",
            })
        climax_candidates.sort(key=lambda x: x["score"], reverse=True)
        primary = climax_candidates[0] if climax_candidates else {"scene_id": "scene_1", "score": 0, "reason": "fallback"}
        graph_edges = len((relationship_graph or {}).get("edges", []))
        conflict_nodes = len((season_conflict_tree or {}).get("conflict_nodes", []))
        return {
            "primary_climax_scene_id": primary["scene_id"],
            "candidates": climax_candidates[:3],
            "escalation_notes": [
                f"关系图边数 {graph_edges}，适合增加人物对撞镜头",
                f"季级冲突节点 {conflict_nodes}，高潮前插入一次误解/揭示",
            ],
            "shot_recipe": ["wide tension frame", "reaction close-up", "insert prop detail", "reversal close-up", "button ending"],
        }
