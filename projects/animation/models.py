
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class CharacterBible:
    name: str
    role: str
    age_range: str
    appearance: List[str] = field(default_factory=list)
    wardrobe: List[str] = field(default_factory=list)
    personality: List[str] = field(default_factory=list)
    voice_style: str = ""
    catchphrases: List[str] = field(default_factory=list)
    continuity_rules: List[str] = field(default_factory=list)
    reference_image_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StoryBible:
    title: str
    genre: str
    format: str
    target_platform: str
    visual_style: str
    tone: str
    logline: str
    world_rules: List[str] = field(default_factory=list)
    recurring_locations: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    camera_language: List[str] = field(default_factory=list)
    rendering_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShotPlan:
    shot_id: str
    scene_id: str
    duration_seconds: float
    camera: str
    framing: str
    action: str
    dialogue: str
    emotion: str
    visual_prompt: str
    continuity_notes: List[str] = field(default_factory=list)
    render_prompt: str = ""
    subtitle_text: str = ""
    reference_image_url: str = ""
    render_duration_seconds: int = 4
    shot_retry_limit: int = 2
    retry_count: int = 0
    template_id: str = ""
    shot_category: str = ""
    negative_prompt: str = ""
    state_assignments: List[dict] = field(default_factory=list)
    scene_assets: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScenePlan:
    scene_id: str
    title: str
    location: str
    dramatic_purpose: str
    beats: List[str] = field(default_factory=list)
    dialogue_summary: List[str] = field(default_factory=list)
    shots: List[ShotPlan] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "title": self.title,
            "location": self.location,
            "dramatic_purpose": self.dramatic_purpose,
            "beats": self.beats,
            "dialogue_summary": self.dialogue_summary,
            "shots": [s.to_dict() for s in self.shots],
        }


@dataclass
class EpisodePlan:
    episode_title: str
    synopsis: str
    hook: str
    cliffhanger: str
    scenes: List[ScenePlan] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "episode_title": self.episode_title,
            "synopsis": self.synopsis,
            "hook": self.hook,
            "cliffhanger": self.cliffhanger,
            "scenes": [s.to_dict() for s in self.scenes],
        }


@dataclass
class AnimationTaskState:
    task_id: str
    status: str
    stage: str
    stage_message: str = ""
    progress: int = 0
    output_video: Optional[str] = None
    subtitle_path: Optional[str] = None
    storyboard_path: Optional[str] = None
    task_dir: Optional[str] = None
    error: Optional[str] = None
    artifacts: dict = field(default_factory=dict)
    plan: Optional[dict] = None
    shot_results: List[dict] = field(default_factory=list)
    batch_parent_id: Optional[str] = None
    batch_children: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
