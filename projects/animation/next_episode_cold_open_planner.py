
from __future__ import annotations
from typing import Any

class NextEpisodeColdOpenPlanner:
    def build(
        self,
        next_season_hook_planner: dict[str, Any],
        finale_payoff_plan: dict[str, Any],
        season_memory_bank: dict[str, Any] | None = None,
        relationship_graph: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        season_memory_bank = season_memory_bank or {}
        relationship_graph = relationship_graph or {}
        hero_payoff = finale_payoff_plan.get("hero_payoff") or {}
        relationship_edges = relationship_graph.get("edges", []) or []
        first_hook = next_season_hook_planner.get("season_opening_hook") or "风暴结束后，代价才刚刚开始。"
        return {
            "cold_open_style": "post-finale aftermath",
            "opening_image": f"承接 {hero_payoff.get('scene_id', '终局场')} 的余震画面",
            "opening_line": first_hook,
            "first_30s_blueprint": [
                "0-8s：直接给后果，不解释前因",
                "8-18s：切角色反应与错位关系",
                "18-30s：抛出新季核心问题并切黑",
            ],
            "carry_over_memory": (season_memory_bank.get("open_loops") or [])[:3],
            "relationship_aftershock": relationship_edges[:2],
            "editor_notes": [
                "冷开场先展示代价，再展示谜面",
                "尽量保留上一季终局余震的情绪颜色和声音纹理",
                "30 秒内不要把 open loop 解释完",
            ],
        }
