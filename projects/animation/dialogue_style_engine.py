
from __future__ import annotations

from typing import Any


class DialogueStyleEngine:
    def build(self, story_bible: dict[str, Any], characters: list[dict[str, Any]], relationship_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        graph = relationship_graph or {}
        edges = graph.get("edges", [])
        styles = {}
        for char in characters:
            name = char.get("name", "")
            role = char.get("role", "")
            personality = "、".join(char.get("personality", [])[:3])
            catch = "；".join(char.get("catchphrases", [])[:2])
            relation_bias = [e.get("dynamic_summary", "") for e in edges if e.get("source") == name or e.get("target") == name][:2]
            styles[name] = {
                "tone": char.get("voice_style", "自然有辨识度"),
                "lexicon_bias": personality or "简洁有张力",
                "rhythm": "短句+停顿+反问" if ("强势" in personality or "理智" in personality) else "自然口语+情绪抬升",
                "catchphrase_memory": catch,
                "relationship_pressure": relation_bias,
                "dialogue_guardrails": [
                    f"保持{name}的角色定位：{role}",
                    "单句不宜过长，保留短剧冲突张力",
                    "对白要能推动剧情或制造关系变化",
                ],
            }
        return {
            "series_tone": story_bible.get("tone", ""),
            "styles": styles,
            "global_rules": [
                "对白优先服务冲突推进，不写空台词",
                "每场至少有一句可剪成短视频切片的钩子台词",
                "角色措辞保持稳定，避免口癖漂移",
            ],
        }

    def apply_to_episode(self, episode, dialogue_styles: dict[str, Any]):
        style_map = dialogue_styles.get("styles", {})
        for scene in getattr(episode, "scenes", []) or []:
            for shot in getattr(scene, "shots", []) or []:
                haystack = f"{getattr(shot, 'dialogue', '')} {getattr(shot, 'action', '')}"
                involved = [name for name in style_map if name and name in haystack]
                if involved:
                    shot.continuity_notes.append(
                        f"对白风格锚点：{style_map[involved[0]].get('tone', '')} / {style_map[involved[0]].get('lexicon_bias', '')}"
                    )
                    try:
                        setattr(shot, "dialogue_style_tags", involved)
                    except Exception:
                        pass
        return episode
