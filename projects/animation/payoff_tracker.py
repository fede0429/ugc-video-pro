from __future__ import annotations

from typing import Any


class PayoffTracker:
    def build(self, foreshadow_payload: dict[str, Any], twist_report: dict[str, Any], climax_plan: dict[str, Any]) -> dict[str, Any]:
        strongest = twist_report.get("strongest_twist") or {}
        climax_scene = (climax_plan.get("primary_climax_scene") or {}).get("scene_id")
        payoffs = []
        for seed in foreshadow_payload.get("foreshadow_seeds", []):
            payoffs.append({
                "seed_scene_id": seed.get("scene_id"),
                "payoff_scene_id": seed.get("payoff_target") or strongest.get("scene_id") or climax_scene,
                "payoff_mode": "reaction payoff + insert detail",
                "strength": 78 if seed.get("payoff_target") == strongest.get("scene_id") else 66,
            })
        return {
            "payoffs": payoffs,
            "main_payoff_scene": strongest.get("scene_id") or climax_scene,
            "payoff_notes": [
                "埋点不要直接解释，高潮处再补全信息闭环。",
                "高潮镜头优先展示人物反应，再切证据或道具细节。",
            ],
        }
