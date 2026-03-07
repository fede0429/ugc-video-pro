from __future__ import annotations

from typing import List
from .models import CharacterBible, EpisodePlan


class ContinuityEngine:
    def validate(self, episode: EpisodePlan, characters: List[CharacterBible], consistency_report: dict | None = None) -> dict:
        warnings: List[str] = []
        suggestions: List[str] = []
        character_names = {c.name for c in characters}
        template_ids = set()
        if not episode.scenes:
            warnings.append("当前分集没有 scene。")
        for scene in episode.scenes:
            if not scene.shots:
                warnings.append(f"{scene.scene_id} 缺少 shots。")
            for shot in scene.shots:
                if not (shot.visual_prompt or "").strip():
                    warnings.append(f"{shot.shot_id} 缺少 visual_prompt。")
                if shot.duration_seconds <= 0:
                    warnings.append(f"{shot.shot_id} 时长必须大于 0。")
                if not shot.subtitle_text and shot.dialogue and shot.dialogue != "无对白":
                    suggestions.append(f"{shot.shot_id} 建议补 subtitle_text。")
                if len(shot.continuity_notes) < 2:
                    warnings.append(f"{shot.shot_id} continuity notes 偏少。")
                state_note_count = sum(1 for note in shot.continuity_notes if str(note).startswith("character_state:"))
                asset_note_count = sum(1 for note in shot.continuity_notes if str(note).startswith("scene_asset:"))
                if state_note_count == 0:
                    warnings.append(f"{shot.shot_id} 缺少角色状态锚点。")
                if asset_note_count == 0:
                    suggestions.append(f"{shot.shot_id} 缺少场景资产锚点，后续镜头一致性可能偏弱。")
                if not shot.template_id:
                    suggestions.append(f"{shot.shot_id} 未绑定 template_id，后续重切分镜会不稳定。")
                else:
                    template_ids.add(shot.template_id)
        if len(character_names) == 0:
            warnings.append("当前项目没有角色设定。")
        response = {
            "ok": not warnings,
            "warning_count": len(warnings),
            "warnings": warnings,
            "suggestions": suggestions,
            "character_count": len(character_names),
            "scene_count": len(episode.scenes),
            "shot_count": sum(len(scene.shots) for scene in episode.scenes),
            "template_count": len(template_ids),
            "state_anchor_shots": sum(1 for scene in episode.scenes for shot in scene.shots if any(str(note).startswith("character_state:") for note in shot.continuity_notes)),
            "scene_asset_anchor_shots": sum(1 for scene in episode.scenes for shot in scene.shots if any(str(note).startswith("scene_asset:") for note in shot.continuity_notes)),
        }
        if consistency_report:
            response["consistency"] = consistency_report
            response["ok"] = response["ok"] and consistency_report.get("consistency_score", 0) >= 60
        return response
