
from __future__ import annotations

from itertools import combinations


class RelationshipGraphBuilder:
    def build(self, story_bible, characters, episode=None) -> dict:
        nodes = []
        edges = []
        for char in characters:
            nodes.append({
                "id": char.name,
                "label": char.name,
                "role": char.role,
                "traits": list(char.personality or [])[:4],
            })
        for left, right in combinations(characters, 2):
            relation_type = self._infer_relation(left, right, story_bible.genre)
            tension = self._infer_tension(left, right)
            shared_motifs = sorted(set((left.catchphrases or [])[:1] + (right.catchphrases or [])[:1]))
            edges.append({
                "source": left.name,
                "target": right.name,
                "relation_type": relation_type,
                "tension_level": tension,
                "shared_motifs": shared_motifs,
                "dynamic_summary": f"{left.name} 与 {right.name} 当前更偏 {relation_type}，张力等级 {tension}/10。",
            })
        central_conflict = f"{story_bible.title} 围绕 {story_bible.logline[:80]} 展开。"
        if episode:
            central_conflict += f" 本集钩子：{episode.hook}"
        return {
            "nodes": nodes,
            "edges": edges,
            "central_conflict": central_conflict,
            "graph_summary": f"角色数 {len(nodes)}，关系边 {len(edges)}。",
        }

    def _infer_relation(self, left, right, genre: str) -> str:
        pair = " ".join([left.role, right.role, genre]).lower()
        if any(k in pair for k in ["女主", "男主", "romance", "情感"]):
            return "rivals_to_lovers"
        if any(k in pair for k in ["反派", "boss", "豪门"]):
            return "power_conflict"
        return "alliance_with_friction"

    def _infer_tension(self, left, right) -> int:
        score = 5
        if set(left.personality or []) & {"强势", "嘴硬", "理智"}:
            score += 1
        if set(right.personality or []) & {"强势", "嘴硬", "理智"}:
            score += 1
        if left.role != right.role:
            score += 1
        return min(9, score)
