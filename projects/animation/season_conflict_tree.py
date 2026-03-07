
from __future__ import annotations

from typing import Any


class SeasonConflictTree:
    def build(
        self,
        story_bible: dict[str, Any],
        relationship_graph: dict[str, Any],
        story_memory_bank: dict[str, Any],
        previous_memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        edges = relationship_graph.get("edges", [])
        conflicts = []
        for edge in edges[:8]:
            conflicts.append({
                "conflict_id": f"{edge.get('source','A')}_{edge.get('target','B')}",
                "parties": [edge.get("source", ""), edge.get("target", "")],
                "type": edge.get("relationship_type", "tension"),
                "summary": edge.get("dynamic_summary", ""),
                "stakes": "关系破裂 / 目标失手 / 身份暴露",
            })
        open_loops = list(story_memory_bank.get("open_loops", []))
        inherited = (previous_memory or {}).get("open_loops", [])[:3]
        if inherited:
            open_loops.extend([f"继承线索：{item}" for item in inherited])
        return {
            "season_id": story_memory_bank.get("season_id") or story_bible.get("title", "default_season"),
            "core_conflict": story_bible.get("logline", "") or story_bible.get("core_premise", ""),
            "conflict_nodes": conflicts,
            "open_loops": open_loops[:12],
            "escalation_path": [
                "误会/利益绑定",
                "关系升级/秘密扩大",
                "核心冲突正面爆发",
                "代价兑现与反转",
            ],
        }
