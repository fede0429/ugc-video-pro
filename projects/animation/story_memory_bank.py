
from __future__ import annotations

from copy import deepcopy


class StoryMemoryBank:
    def build(self, story_bible, characters, episode, relationship_graph: dict, previous_memory: dict | None = None, episode_index: int = 1) -> dict:
        memory = deepcopy(previous_memory or {})
        episodic_beats = memory.get("episodic_beats", [])
        current_beat = {
            "episode_index": episode_index,
            "episode_title": episode.episode_title,
            "goal": episode.synopsis,
            "hook": episode.hook,
            "cliffhanger": episode.cliffhanger,
        }
        episodic_beats.append(current_beat)
        character_arcs = memory.get("character_arcs", {})
        for char in characters:
            arc = character_arcs.get(char.name, {
                "baseline_traits": list(char.personality or []),
                "recent_states": [],
                "unresolved_threads": [],
            })
            arc["recent_states"] = (arc.get("recent_states", []) + [{
                "episode_index": episode_index,
                "emotional_drive": self._infer_drive(char),
                "wardrobe_anchor": (char.wardrobe or [""])[0],
            }])[-5:]
            if episode.cliffhanger:
                arc["unresolved_threads"] = list(dict.fromkeys((arc.get("unresolved_threads", []) + [episode.cliffhanger])))[-5:]
            character_arcs[char.name] = arc
        memory.update({
            "series_title": story_bible.title,
            "episode_count": len(episodic_beats),
            "episodic_beats": episodic_beats,
            "character_arcs": character_arcs,
            "relationship_graph_snapshot": relationship_graph,
            "open_loops": self._derive_open_loops(episode, relationship_graph),
            "continuity_anchors": self._continuity_anchors(story_bible, characters),
        })
        return memory

    def _infer_drive(self, char) -> str:
        traits = " ".join(char.personality or [])
        if "理智" in traits:
            return "控制局面"
        if "嘴硬" in traits:
            return "隐藏真实心意"
        if "强势" in traits:
            return "掌控关系主动权"
        return "推进冲突"

    def _derive_open_loops(self, episode, relationship_graph: dict) -> list[str]:
        loops = [episode.cliffhanger] if episode.cliffhanger else []
        for edge in relationship_graph.get("edges", [])[:2]:
            loops.append(f"{edge['source']} 与 {edge['target']} 的 {edge['relation_type']} 仍未解决")
        return [l for l in loops if l]

    def _continuity_anchors(self, story_bible, characters) -> dict:
        return {
            "visual_style": story_bible.visual_style,
            "recurring_locations": list(story_bible.recurring_locations or []),
            "character_wardrobe": {c.name: list(c.wardrobe or [])[:2] for c in characters},
        }
