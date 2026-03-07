
from __future__ import annotations

from typing import List
from .models import CharacterBible, EpisodePlan, ShotPlan
from .shot_template_library import ShotTemplateLibrary


class StoryboardGenerator:
    def __init__(self, template_library: ShotTemplateLibrary | None = None):
        self.template_library = template_library or ShotTemplateLibrary()

    def build_shots(
        self,
        episode: EpisodePlan,
        characters: List[CharacterBible],
        visual_style: str,
    ) -> EpisodePlan:
        hero = characters[0].name if characters else "主角"
        rival = characters[1].name if len(characters) > 1 else "对手"
        support = characters[2].name if len(characters) > 2 else hero
        for scene in episode.scenes:
            scene_templates = [
                self.template_library.choose_template(scene.dramatic_purpose, 0),
                self.template_library.choose_template(scene.dramatic_purpose, 1),
                self.template_library.choose_template("信息反转" if scene.dramatic_purpose != "高潮推进" else "高潮推进", 0),
            ]
            shots: List[ShotPlan] = []
            for idx, template in enumerate(scene_templates):
                action = template.action_pattern.format(
                    hero=hero,
                    rival=rival,
                    support=support,
                    location=scene.location,
                )
                dialogue = template.dialogue_pattern.format(
                    hero=hero,
                    rival=rival,
                    support=support,
                    location=scene.location,
                )
                prompt_keywords = ", ".join(template.prompt_keywords)
                continuity = list(template.continuity_hints)
                continuity.append(f"scene purpose: {scene.dramatic_purpose}")
                continuity.append(f"beat anchor: {(scene.beats[idx % len(scene.beats)] if scene.beats else scene.title)}")
                shot = ShotPlan(
                    shot_id=f"{scene.scene_id}_shot_{idx+1}",
                    scene_id=scene.scene_id,
                    duration_seconds=template.default_duration_seconds,
                    camera=template.camera,
                    framing=template.framing,
                    action=action,
                    dialogue=dialogue,
                    emotion=scene.dramatic_purpose,
                    visual_prompt=f"{visual_style}, {scene.location}, {action}, {template.camera}, {template.framing}, {prompt_keywords}",
                    continuity_notes=continuity,
                    subtitle_text=dialogue if dialogue != "无对白" else "",
                    render_duration_seconds=int(round(template.default_duration_seconds)),
                    template_id=template.template_id,
                    shot_category=template.category,
                    negative_prompt="low consistency, face drift, random costume changes, anatomy errors",
                )
                shots.append(shot)
            scene.shots = shots
        return episode
