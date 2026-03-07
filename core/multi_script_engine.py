
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Any

from services.video_scoring_service import VideoScoringService


@dataclass
class ScriptBatchCandidate:
    variant_id: str
    hook_style: str
    hook_line: str
    timeline: dict[str, Any]
    creative_score: dict[str, Any]
    selection_reason: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultiScriptBatchEngine:
    def __init__(self, script_generator, scorer: VideoScoringService | None = None):
        self.script_generator = script_generator
        self.scorer = scorer or VideoScoringService()

    async def generate(
        self,
        request,
        product_profile,
        presenter_profile,
        production_plan,
        max_scripts: int = 3,
    ) -> dict[str, Any]:
        variants = list(getattr(production_plan, "variants", []) or [])
        if not variants:
            timeline = await self.script_generator.generate_timeline(
                request=request,
                product_profile=product_profile,
                presenter_profile=presenter_profile,
                production_plan=production_plan,
            )
            score = self.scorer.score(timeline, None).to_dict()
            candidate = ScriptBatchCandidate(
                variant_id=getattr(production_plan, "selected_variant_id", "default"),
                hook_style=getattr(production_plan, "hook_style", "result_first"),
                hook_line=(timeline.segments[0].spoken_line if timeline.segments else ""),
                timeline=timeline.to_dict(),
                creative_score=score,
                selection_reason=["fallback_single_timeline"],
            )
            return {
                "selected_variant_id": candidate.variant_id,
                "selected_script_id": candidate.variant_id,
                "selected_creative_score": candidate.creative_score,
                "candidates": [candidate.to_dict()],
                "selected_timeline": timeline,
            }

        candidates: list[ScriptBatchCandidate] = []
        dedup: set[str] = set()
        for idx, variant in enumerate(variants[:max_scripts], start=1):
            hook_style = variant.get("hook_style") or getattr(production_plan, "hook_style", "result_first")
            hook_line = variant.get("hook_line") or ""
            signature = f"{hook_style}|{hook_line}"
            if signature in dedup:
                continue
            dedup.add(signature)

            candidate_plan = deepcopy(production_plan)
            candidate_plan.selected_variant_id = variant.get("variant_id", f"variant_{idx:02d}")
            candidate_plan.hook_style = hook_style
            candidate_plan.variants = variants
            candidate_plan.reasoning = list(getattr(production_plan, "reasoning", []) or []) + [f"batch_candidate={candidate_plan.selected_variant_id}"]

            updated_segments = []
            for s_index, seg in enumerate(list(getattr(production_plan, "segments_json", []) or [])):
                item = dict(seg)
                if s_index == 0:
                    if item.get("track") == "a_roll":
                        item["spoken_line"] = hook_line or item.get("spoken_line", "")
                    item["overlay_text"] = variant.get("overlay_override") or item.get("overlay_text") or ""
                    item["scene_purpose"] = "hook"
                    item["hook_style"] = hook_style
                updated_segments.append(item)
            candidate_plan.segments_json = updated_segments

            timeline = await self.script_generator.generate_timeline(
                request=request,
                product_profile=product_profile,
                presenter_profile=presenter_profile,
                production_plan=candidate_plan,
            )
            creative_score = self.scorer.score(timeline, None).to_dict()
            creative_score["hook_score"] = variant.get("hook_score", {})
            candidates.append(ScriptBatchCandidate(
                variant_id=candidate_plan.selected_variant_id,
                hook_style=hook_style,
                hook_line=hook_line,
                timeline=timeline.to_dict(),
                creative_score=creative_score,
                selection_reason=list(variant.get("notes", []))[:4] + [f"hook_style={hook_style}"],
            ))

        candidates.sort(
            key=lambda c: (
                c.creative_score.get("total_score", 0),
                c.creative_score.get("hook_score", {}).get("total_score", 0),
                c.creative_score.get("hook_strength_score", 0),
            ),
            reverse=True,
        )
        selected = candidates[0]
        return {
            "selected_variant_id": selected.variant_id,
            "selected_script_id": selected.variant_id,
            "selected_creative_score": selected.creative_score,
            "candidates": [c.to_dict() for c in candidates],
            "selected_timeline": candidates[0].timeline,
        }
