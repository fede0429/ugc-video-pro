from __future__ import annotations

from typing import List
from .models import CharacterBible, EpisodePlan


class CharacterConsistencyEngine:
    def build_profiles(self, characters: List[CharacterBible]) -> dict:
        profiles = {}
        for character in characters:
            profiles[character.name] = {
                "role": character.role,
                "appearance_anchor": list(character.appearance[:4]),
                "wardrobe_anchor": list(character.wardrobe[:3]),
                "personality_anchor": list(character.personality[:3]),
                "voice_style": character.voice_style,
                "continuity_rules": list(character.continuity_rules),
                "reference_image_url": character.reference_image_url or "",
            }
        return profiles

    def apply_to_episode(self, episode: EpisodePlan, characters: List[CharacterBible]) -> dict:
        profiles = self.build_profiles(characters)
        hero_reference = next((c.reference_image_url for c in characters if c.reference_image_url), "")
        for scene in episode.scenes:
            for shot in scene.shots:
                for character in characters[:3]:
                    anchor_bits = []
                    if character.appearance:
                        anchor_bits.append(f"{character.name} appearance: {', '.join(character.appearance[:3])}")
                    if character.wardrobe:
                        anchor_bits.append(f"{character.name} wardrobe: {', '.join(character.wardrobe[:2])}")
                    if anchor_bits:
                        for bit in anchor_bits[:2]:
                            if bit not in shot.continuity_notes:
                                shot.continuity_notes.append(bit)
                if hero_reference and not shot.reference_image_url:
                    shot.reference_image_url = hero_reference
                shot.continuity_notes = list(dict.fromkeys(shot.continuity_notes))
        return profiles

    def evaluate(self, episode: EpisodePlan, characters: List[CharacterBible]) -> dict:
        profiles = self.build_profiles(characters)
        warnings = []
        suggestions = []
        score = 100
        for scene in episode.scenes:
            for shot in scene.shots:
                note_text = " | ".join(shot.continuity_notes)
                for character in characters:
                    if not any(character.name in (shot.action or "") or character.name in (shot.dialogue or "") or character.name in note_text for _ in [0]):
                        continue
                    if not character.appearance:
                        warnings.append(f"{character.name} 缺少 appearance 锚点，{shot.shot_id} 的一致性会变弱。")
                        score -= 4
                    if not character.wardrobe:
                        suggestions.append(f"{character.name} 建议补 wardrobe 锚点，提升 {shot.shot_id} 服装连续性。")
                        score -= 1
                if len(shot.continuity_notes) < 2:
                    warnings.append(f"{shot.shot_id} continuity notes 偏少。")
                    score -= 3
                if not shot.reference_image_url:
                    suggestions.append(f"{shot.shot_id} 未绑定角色参考图，建议至少给主角一张参考图。")
                    score -= 1
        score = max(0, min(100, score))
        return {
            "consistency_score": score,
            "profiles": profiles,
            "warnings": list(dict.fromkeys(warnings)),
            "suggestions": list(dict.fromkeys(suggestions)),
        }
