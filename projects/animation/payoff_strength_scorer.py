
from __future__ import annotations

class PayoffStrengthScorer:
    def build(
        self,
        foreshadow_plan: dict | None = None,
        payoff_tracker: dict | None = None,
        climax_plan: dict | None = None,
        relationship_graph: dict | None = None,
    ) -> dict:
        payoffs = list((payoff_tracker or {}).get("payoffs", []))
        climax_scene = (climax_plan or {}).get("primary_climax_scene")
        edges = (relationship_graph or {}).get("edges", [])
        scores = []
        for item in payoffs:
            score = 55
            if item.get("payoff_scene_id") == climax_scene:
                score += 18
            if item.get("strength", 0) >= 80:
                score += 10
            if edges:
                score += 5
            scores.append({
                "seed_scene_id": item.get("seed_scene_id"),
                "payoff_scene_id": item.get("payoff_scene_id"),
                "score": min(98, score),
                "note": "回收已接近高潮位置，建议保留角色反应镜头。" if item.get("payoff_scene_id") == climax_scene else "建议补更明确的对白或反应镜头。",
            })
        overall = round(sum(x["score"] for x in scores) / len(scores), 1) if scores else 0.0
        best = max(scores, key=lambda x: x["score"]) if scores else None
        weak = [x for x in scores if x["score"] < 70]
        notes = []
        if weak:
            notes.append("存在回收偏弱的埋点，建议补 reaction shot / payoff 台词。")
        if best:
            notes.append(f"优先保留 {best['seed_scene_id']} -> {best['payoff_scene_id']} 这条回收链。")
        return {
            "payoff_scores": scores,
            "overall_strength": overall,
            "best_payoff": best,
            "weak_payoffs": weak,
            "revision_notes": notes,
        }

    def apply_to_episode(self, episode_obj, payoff_strength: dict) -> None:
        best = (payoff_strength or {}).get("best_payoff") or {}
        weak_ids = {(item.get("seed_scene_id"), item.get("payoff_scene_id")) for item in (payoff_strength or {}).get("weak_payoffs", [])}
        for scene in getattr(episode_obj, "scenes", []):
            for shot in getattr(scene, "shots", []):
                if best and scene.scene_id == best.get("payoff_scene_id"):
                    shot.continuity_notes.append("强回收场：给角色反应和落点台词留空间。")
                if any(scene.scene_id in pair for pair in weak_ids):
                    shot.continuity_notes.append("弱回收提示：建议补表情、停顿或更清晰的回答。")
