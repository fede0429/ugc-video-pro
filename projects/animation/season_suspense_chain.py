
from __future__ import annotations

from typing import Any


class SeasonSuspenseChain:
    def build(self, season_memory_bank: dict[str, Any] | None, story_memory_bank: dict[str, Any] | None,
              suspense_keeper: dict[str, Any] | None, scene_twists: dict[str, Any] | None,
              climax_plan: dict[str, Any] | None, batch_parent_id: str | None = None) -> dict[str, Any]:
        season_memory_bank = season_memory_bank or {}
        story_memory_bank = story_memory_bank or {}
        suspense_keeper = suspense_keeper or {}
        scene_twists = scene_twists or {}
        climax_plan = climax_plan or {}

        open_loops = list(story_memory_bank.get("open_loops", []))
        season_arcs = list(season_memory_bank.get("season_arcs", []))
        twist_scenes = list(scene_twists.get("twist_scenes", []))
        cliffhangers = list(suspense_keeper.get("cliffhanger_candidates", []))

        chain = []
        chain_id = 1
        for idx, item in enumerate(cliffhangers):
            loop_text = open_loops[idx] if idx < len(open_loops) else (season_arcs[idx] if idx < len(season_arcs) else item.get("hook"))
            chain.append({
                "chain_id": f"ssc_{chain_id}",
                "seed_scene_id": item.get("scene_id"),
                "mid_hold_scene_id": item.get("scene_id"),
                "cliffhanger": item.get("hook"),
                "season_question": loop_text or "关键真相尚未完全揭露",
                "priority": round(78 - idx * 4, 1),
            })
            chain_id += 1

        strongest_twist = scene_twists.get("strongest_twist") or {}
        if strongest_twist:
            chain.append({
                "chain_id": f"ssc_{chain_id}",
                "seed_scene_id": strongest_twist.get("scene_id"),
                "mid_hold_scene_id": strongest_twist.get("scene_id"),
                "cliffhanger": strongest_twist.get("twist") or "核心身份关系出现翻转",
                "season_question": "这场反转会在后续哪一集彻底兑现？",
                "priority": 92.0,
            })

        chain.sort(key=lambda x: x.get("priority", 0), reverse=True)
        strongest_chain = chain[0] if chain else None
        retention_target = max(float(suspense_keeper.get("suspense_index", 55.0)), 55.0)
        return {
            "batch_parent_id": batch_parent_id,
            "season_chain": chain,
            "strongest_chain": strongest_chain,
            "season_questions": [c["season_question"] for c in chain[:5]],
            "recommended_tease_density": "每集至少1个中段悬念 + 1个尾钩",
            "retention_target": round(retention_target, 1),
        }

    def apply_to_episode(self, episode, season_suspense_chain: dict[str, Any] | None) -> None:
        if not season_suspense_chain:
            return
        strongest = (season_suspense_chain or {}).get("strongest_chain") or {}
        seed_scene_id = strongest.get("seed_scene_id")
        season_question = strongest.get("season_question")
        if not seed_scene_id:
            return
        for scene in getattr(episode, "scenes", []):
            if scene.scene_id == seed_scene_id:
                for shot in getattr(scene, "shots", []):
                    if season_question:
                        shot.continuity_notes.append(f"季级悬念链：{season_question}")
