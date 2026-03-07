from __future__ import annotations

from typing import Any

class PunchlineDialogueGenerator:
    def build(self, episode: dict[str, Any], relationship_graph: dict[str, Any] | None = None, dialogue_styles: dict[str, Any] | None = None) -> dict[str, Any]:
        graph = relationship_graph or {}
        edge_summaries = [e.get("dynamic_summary", "") for e in graph.get("edges", []) if e.get("dynamic_summary")]
        styles = (dialogue_styles or {}).get("styles", {})
        scene_lines = []
        for idx, scene in enumerate(episode.get("scenes", [])):
            label = scene.get("dramatic_purpose", "冲突推进")
            style_hint = ""
            if styles:
                first_name = next(iter(styles.keys()))
                style_hint = styles[first_name].get("tone", "")
            line = f"{label}不是结束，是你们翻脸的开始。"
            if idx == 0:
                line = f"你以为你赢了？好戏才刚开始。"
            elif idx == len(episode.get("scenes", [])) - 1:
                line = f"今天这一步，我迟早会让你们全部还回来。"
            if style_hint:
                line = f"{line}（{style_hint}）"
            scene_lines.append({
                "scene_id": scene.get("scene_id"),
                "punchline": line,
                "usage": "scene_closer" if idx else "opening_hook",
                "relation_hint": edge_summaries[idx % len(edge_summaries)] if edge_summaries else "",
            })
        return {
            "lines": scene_lines,
            "global_rules": [
                "台词必须短、狠、可切片",
                "一句话要有冲突指向，不写空抒情",
                "优先放在每场戏结尾或转场前",
            ],
        }

    def apply_to_episode(self, episode, payload: dict[str, Any]):
        line_map = {item.get("scene_id"): item for item in payload.get("lines", [])}
        for scene in getattr(episode, "scenes", []) or []:
            item = line_map.get(getattr(scene, "scene_id", ""))
            if not item:
                continue
            shots = getattr(scene, "shots", []) or []
            if not shots:
                continue
            target = shots[-1]
            if not getattr(target, "dialogue", "") or getattr(target, "dialogue", "") == "无对白":
                target.dialogue = item.get("punchline", "")
                target.subtitle_text = item.get("punchline", "")
            else:
                target.continuity_notes.append("爆点台词候选：" + item.get("punchline", ""))
            try:
                setattr(target, "punchline_candidate", item.get("punchline", ""))
            except Exception:
                pass
        return episode
