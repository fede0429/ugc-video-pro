
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AnimationCharacterInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    role: str = Field(min_length=1, max_length=100)
    age_range: str = Field(default="18-25", max_length=50)
    appearance: List[str] = Field(default_factory=list)
    wardrobe: List[str] = Field(default_factory=list)
    personality: List[str] = Field(default_factory=list)
    voice_style: str = Field(default="清晰、年轻、有辨识度", max_length=200)
    catchphrases: List[str] = Field(default_factory=list)
    reference_image_url: Optional[str] = Field(default="")


class AnimationPlanRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    genre: str = Field(default="都市情感", max_length=80)
    format_type: str = Field(default="竖屏短剧", max_length=80)
    target_platform: str = Field(default="douyin", max_length=50)
    visual_style: str = Field(default="high consistency anime cinematic", max_length=300)
    tone: str = Field(default="高张力、强反转", max_length=200)
    core_premise: str = Field(min_length=1, max_length=500)
    episode_goal: str = Field(min_length=1, max_length=300)
    scene_count: int = Field(default=4, ge=3, le=8)
    characters: List[AnimationCharacterInput] = Field(default_factory=list)
    language: str = Field(default="zh", pattern="^(zh|en|it)$")
    aspect_ratio: str = Field(default="9:16", max_length=10)
    model_variant: str = Field(default="seedance_2", max_length=50)
    fallback_model: str = Field(default="seedance_15", max_length=50)
    enable_tts: bool = True
    dry_run: bool = False
    shot_retry_limit: int = Field(default=2, ge=0, le=5)
    batch_parent_id: Optional[str] = Field(default="")
    episode_index: int = Field(default=1, ge=1, le=999)
    reuse_assets_across_episodes: bool = True


class AnimationPlanResponse(BaseModel):
    story_bible: dict
    characters: List[dict]
    episode: dict
    consistency_report: dict = Field(default_factory=dict)
    continuity_report: dict
    shot_templates: List[dict] = Field(default_factory=list)
    consistency_profiles: dict = Field(default_factory=dict)
    character_states: dict = Field(default_factory=dict)
    scene_assets: dict = Field(default_factory=dict)
    scene_state_flow: dict = Field(default_factory=dict)
    episode_asset_reuse: dict = Field(default_factory=dict)
    relationship_graph: dict = Field(default_factory=dict)
    story_memory_bank: dict = Field(default_factory=dict)
    outline_editor: dict = Field(default_factory=dict)
    season_memory_bank: dict = Field(default_factory=dict)
    dialogue_styles: dict = Field(default_factory=dict)
    season_conflict_tree: dict = Field(default_factory=dict)
    scene_pacing: dict = Field(default_factory=dict)
    climax_plan: dict = Field(default_factory=dict)
    emotion_arcs: dict = Field(default_factory=dict)
    punchline_dialogue: dict = Field(default_factory=dict)
    scene_twists: dict = Field(default_factory=dict)
    highlight_shots: dict = Field(default_factory=dict)
    shot_emotion_filters: dict = Field(default_factory=dict)
    foreshadow_plan: dict = Field(default_factory=dict)
    payoff_tracker: dict = Field(default_factory=dict)
    render_meta: dict


class AnimationRenderResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    stage_message: str
    task_dir: Optional[str] = None


class AnimationTaskResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    stage_message: str
    progress: int = 0
    output_video: Optional[str] = None
    subtitle_path: Optional[str] = None
    storyboard_path: Optional[str] = None
    task_dir: Optional[str] = None
    error: Optional[str] = None
    artifacts: dict = Field(default_factory=dict)
    plan: Optional[dict] = None
    shot_results: List[dict] = Field(default_factory=list)
    batch_parent_id: Optional[str] = None
    batch_children: List[str] = Field(default_factory=list)


class AnimationTaskListResponse(BaseModel):
    items: List[AnimationTaskResponse]


class AnimationReferenceUploadResponse(BaseModel):
    asset_id: str
    character_name: str
    file_name: str
    local_path: str
    asset_url: str


class AnimationShotRetryRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=80)
    task_id: str = Field(min_length=1, max_length=80)


class AnimationBatchRenderRequest(AnimationPlanRequest):
    episode_goals: List[str] = Field(default_factory=list, min_length=1, max_length=12)
    title_prefix: Optional[str] = Field(default="")


class AnimationBatchRenderResponse(BaseModel):
    batch_task_id: str
    task_ids: List[str] = Field(default_factory=list)
    status: str
    stage: str
    stage_message: str


class AnimationOutlineEditorRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    core_premise: str = Field(min_length=1, max_length=500)
    episode_goal: str = Field(min_length=1, max_length=300)
    scene_count: int = Field(default=4, ge=3, le=8)
    batch_parent_id: Optional[str] = Field(default="")


class AnimationOutlineEditorResponse(BaseModel):
    outline: dict


class AnimationSeasonMemoryResponse(BaseModel):
    season_memory: dict
