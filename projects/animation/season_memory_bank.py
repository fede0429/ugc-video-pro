from __future__ import annotations

from typing import Any


class SeasonMemoryBank:
    def build(self, story_bible: dict, relationship_graph: dict, episode: dict, batch_memory: dict | None = None) -> dict[str, Any]:
        previous_arcs = (batch_memory or {}).get("season_arcs", [])
        episode_title = episode.get("episode_title", "")
        relationships = relationship_graph.get("edges", []) if isinstance(relationship_graph, dict) else []
        major_arc = {
            "arc_id": f"arc_{len(previous_arcs)+1:02d}",
            "label": episode_title or story_bible.get("title", "主线"),
            "focus": episode.get("hook", "") or "角色关系推进",
            "relationship_pressure": [e.get("type", "") for e in relationships[:3]],
        }
        season_arcs = previous_arcs + [major_arc]
        memory = {
            "season_id": (batch_memory or {}).get("season_id") or f"{story_bible.get('title','season')}_season_01",
            "story_title": story_bible.get("title", ""),
            "season_arcs": season_arcs[-12:],
            "persistent_symbols": story_bible.get("themes", [])[:6],
            "location_memory": story_bible.get("recurring_locations", [])[:8],
            "open_loops": list(dict.fromkeys(((batch_memory or {}).get("open_loops", []) + [episode.get("cliffhanger", "")])))[:10],
            "character_memory": (batch_memory or {}).get("character_memory", {}),
            "season_notes": [
                "跨集维持人物核心欲望不变，只升级阻碍和代价。",
                "重复使用关键地点和视觉符号，增强系列辨识度。",
            ],
        }
        return memory

    def merge_into_batch(self, existing: dict | None, current: dict) -> dict:
        existing = existing or {}
        merged = dict(existing)
        merged["season_id"] = current.get("season_id") or existing.get("season_id")
        merged["story_title"] = current.get("story_title") or existing.get("story_title")
        merged["season_arcs"] = ((existing.get("season_arcs", []) + current.get("season_arcs", [])))[-20:]
        merged["persistent_symbols"] = list(dict.fromkeys(existing.get("persistent_symbols", []) + current.get("persistent_symbols", [])))[:12]
        merged["location_memory"] = list(dict.fromkeys(existing.get("location_memory", []) + current.get("location_memory", [])))[:12]
        merged["open_loops"] = list(dict.fromkeys(existing.get("open_loops", []) + current.get("open_loops", [])))[:16]
        merged["character_memory"] = {**existing.get("character_memory", {}), **current.get("character_memory", {})}
        merged["season_notes"] = current.get("season_notes", []) or existing.get("season_notes", [])
        return merged
