
from __future__ import annotations
from typing import Any

class TrailerEditor:
    def build(
        self,
        season_trailer_generator: dict[str, Any],
        highlight_shots: dict[str, Any] | None = None,
        suspense_keeper: dict[str, Any] | None = None,
        climax_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        highlight_shots = highlight_shots or {}
        suspense_keeper = suspense_keeper or {}
        climax_plan = climax_plan or {}
        hero = highlight_shots.get("hero_highlight") or {}
        beats = list(season_trailer_generator.get("trailer_beats", []) or [])
        hero_cut = {
            "shot_id": hero.get("shot_id", "hero-cut-1"),
            "purpose": "hero_highlight",
            "editorial_hint": "作为 trailer 中段最高能量镜头，时长控制 0.8~1.2 秒",
        }
        return {
            "cut_style": "vertical high-intensity anime trailer",
            "recommended_duration_seconds": season_trailer_generator.get("trailer_duration_seconds", 20),
            "hero_cut": hero_cut,
            "beats": beats,
            "music_shape": {
                "intro": "low rumble + mystery pulse",
                "middle": "rising percussion",
                "final_hit": "hard stop before tagline",
            },
            "text_cards": season_trailer_generator.get("text_hooks", [])[:3],
            "spoiler_guardrails": [
                "不要直接给出终局 payoff 全景",
                "高潮镜头只切半句对白或半个动作",
                "强 suspense 场面多用 reaction + 黑场切断",
            ],
            "cliffhanger_tag": suspense_keeper.get("recommended_mid_episode_hook") or "真正的答案，在下一秒之后。",
            "final_sting": (climax_plan.get("hero_climax_scene") or {}).get("scene_id", ""),
        }
