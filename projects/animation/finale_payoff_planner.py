
from __future__ import annotations

from typing import Any


class FinalePayoffPlanner:
    def build(self, season_suspense_chain: dict[str, Any] | None, payoff_tracker: dict[str, Any] | None,
              payoff_strength: dict[str, Any] | None, season_conflict_tree: dict[str, Any] | None,
              season_memory_bank: dict[str, Any] | None) -> dict[str, Any]:
        season_suspense_chain = season_suspense_chain or {}
        payoff_tracker = payoff_tracker or {}
        payoff_strength = payoff_strength or {}
        season_conflict_tree = season_conflict_tree or {}
        season_memory_bank = season_memory_bank or {}

        strongest_chain = season_suspense_chain.get("strongest_chain") or {}
        strongest_payoff = payoff_strength.get("best_payoff") or {}
        core_conflict = season_conflict_tree.get("core_conflict") or "真相、关系与身份的终局碰撞"
        season_arcs = list(season_memory_bank.get("season_arcs", []))
        payoffs = list(payoff_tracker.get("payoffs", []))
        finale_scene_id = strongest_payoff.get("payoff_scene_id") or payoff_tracker.get("main_payoff_scene") or "scene_04"

        payoff_nodes = []
        for idx, item in enumerate(payoffs[:6], start=1):
            payoff_nodes.append({
                "node_id": f"fp_{idx}",
                "seed_scene_id": item.get("seed_scene_id"),
                "payoff_scene_id": item.get("payoff_scene_id"),
                "payoff_mode": item.get("payoff_mode", "reveal"),
                "strength": item.get("strength", 60),
            })

        resolution_recipe = [
            "先兑现最大谎言或秘密",
            "再处理关系站队与情感回收",
            "最后给下季留下一个更大的问题",
        ]
        return {
            "finale_scene_id": finale_scene_id,
            "core_conflict": core_conflict,
            "carry_in_question": strongest_chain.get("season_question") or "最大的悬念必须在终局中给出正面回答",
            "payoff_nodes": payoff_nodes,
            "resolution_recipe": resolution_recipe,
            "season_arc_resolution": season_arcs[:5],
            "finale_intensity_target": max(payoff_strength.get("overall_strength", 65.0), 75.0),
        }

    def apply_to_episode(self, episode, finale_payoff_plan: dict[str, Any] | None) -> None:
        if not finale_payoff_plan:
            return
        finale_scene_id = finale_payoff_plan.get("finale_scene_id")
        core_conflict = finale_payoff_plan.get("core_conflict")
        carry_in_question = finale_payoff_plan.get("carry_in_question")
        for scene in getattr(episode, "scenes", []):
            if scene.scene_id == finale_scene_id:
                for shot in getattr(scene, "shots", []):
                    if core_conflict:
                        shot.continuity_notes.append(f"终局回收：{core_conflict}")
                    if carry_in_question:
                        shot.continuity_notes.append(f"终局回答的问题：{carry_in_question}")
