
from __future__ import annotations

from typing import Any


class NextSeasonHookPlanner:
    def build(
        self,
        season_suspense_chain: dict[str, Any],
        finale_payoff_plan: dict[str, Any],
        relationship_graph: dict[str, Any] | None = None,
        season_memory_bank: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        relationship_graph = relationship_graph or {}
        season_memory_bank = season_memory_bank or {}
        unresolved = list(season_suspense_chain.get("carry_over_questions", []) or [])
        open_loops = list(season_memory_bank.get("open_loops", []) or [])
        if not unresolved:
            unresolved = [f"{item.get('scene_id', '关键场')} 背后的真实动机是什么？" for item in season_suspense_chain.get("suspense_nodes", [])[:2]]
        if not open_loops:
            open_loops = unresolved[:2]

        relationship_hooks = []
        for edge in relationship_graph.get("edges", [])[:3]:
            relationship_hooks.append({
                "pair": f"{edge.get('from')} × {edge.get('to')}",
                "hook": f"{edge.get('from')} 与 {edge.get('to')} 的关系将在下季彻底反转。",
                "pressure": edge.get("tension", "latent"),
            })

        season_open = []
        for idx, loop in enumerate((open_loops + unresolved)[:5], start=1):
            season_open.append({
                "rank": idx,
                "hook_type": "carry_over_mystery" if idx <= 2 else "relationship_aftershock",
                "hook_line": str(loop),
                "why_now": "终局回收后仍留下代价与余震，需要跨季兑现。",
            })

        return {
            "next_season_title_suggestion": "下季引爆点规划",
            "season_opening_hook": season_open[0]["hook_line"] if season_open else "风暴结束后，真正的代价才刚刚开始。",
            "carry_over_hooks": season_open,
            "relationship_hooks": relationship_hooks,
            "cold_open_suggestion": "用上一季最后 3 秒的后果作为下一季第 1 场开场。",
            "marketing_lines": [
                "这一刀不是终局，是下一场风暴的起点",
                "所有人都以为赢了，但真正被改写的是关系",
                "你看到的是收尾，角色看到的却是深渊入口",
            ],
            "season_bridge_notes": [
                "第一集前 20 秒必须承接上季终局余震",
                "不要马上解释全部 open loop，先兑现 1 个，再放大 2 个",
                "用关系错位代替信息直给，让观众继续追",
            ],
        }
