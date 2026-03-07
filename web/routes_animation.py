
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from projects.animation.render_pipeline import AnimationRenderPipeline
from projects.animation.task_store import AnimationTaskStore
from web.schemas_animation import (
    AnimationPlanRequest,
    AnimationPlanResponse,
    AnimationRenderResponse,
    AnimationTaskResponse,
    AnimationTaskListResponse,
    AnimationReferenceUploadResponse,
    AnimationShotRetryRequest,
    AnimationBatchRenderRequest,
    AnimationBatchRenderResponse,
    AnimationOutlineEditorRequest,
    AnimationOutlineEditorResponse,
    AnimationSeasonMemoryResponse,
)

router = APIRouter(prefix="/api/animation", tags=["animation"])


def _get_config() -> dict:
    from web.app import get_app_config
    return get_app_config()



@router.get("/emotion-arcs")
async def preview_emotion_arcs(title: str = "示例短剧", goal: str = "公开对峙后关系失控") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.character_emotion_arc_engine import CharacterEmotionArcEngine
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    return CharacterEmotionArcEngine().build(episode.to_dict(), [c.to_dict() for c in chars])


@router.get("/punchline-dialogue")
async def preview_punchline_dialogue(title: str = "示例短剧", goal: str = "旧情人与现任在发布会正面冲突") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.punchline_dialogue_generator import PunchlineDialogueGenerator
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    return PunchlineDialogueGenerator().build(episode.to_dict(), graph, {})




@router.get("/suspense-keeper")
async def preview_suspense_keeper(title: str = "示例短剧", goal: str = "真相只露半张牌") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.suspense_keeper import SuspenseKeeper
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    ep = episode.to_dict()
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    twists = SceneTwistDetector().build(ep)
    climax = ClimaxOrchestrator().build(ep, graph, {"core_conflict": "身份与情感双冲突"})
    foreshadow = ForeshadowPlanter().build(ep, twists, graph)
    return SuspenseKeeper().build(ep, twists, foreshadow, climax)


@router.get("/payoff-strength")
async def preview_payoff_strength(title: str = "示例短剧", goal: str = "旧秘密在发布会上被回收") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.payoff_tracker import PayoffTracker
    from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    ep = episode.to_dict()
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    twists = SceneTwistDetector().build(ep)
    climax = ClimaxOrchestrator().build(ep, graph, {"core_conflict": "身份与情感双冲突"})
    foreshadow = ForeshadowPlanter().build(ep, twists, graph)
    payoff = PayoffTracker().build(foreshadow, twists, climax)
    return PayoffStrengthScorer().build(foreshadow, payoff, climax, graph)
@router.get("/health")
async def animation_health() -> dict:
    return {
        "ok": True,
        "module": "animation_studio",
        "stage": "render_ready",
        "provider": "kie.ai",
        "default_model": "seedance_2",
        "fallback_model": "seedance_15",
    }


@router.get("/templates")
async def list_animation_shot_templates() -> dict:
    from projects.animation.shot_template_library import ShotTemplateLibrary
    library = ShotTemplateLibrary()
    return {"items": library.list_templates(), "count": len(library.templates)}



@router.get("/states")
async def list_animation_character_states() -> dict:
    from projects.animation.character_state_machine import CharacterStateMachine
    from projects.animation.character_bible import build_character_bible
    demo_chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发", "冷白皮"], ["黑色西装裙"], ["理智"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发", "干净轮廓"], ["白衬衫"], ["聪明"], "自然"),
    ]
    machine = CharacterStateMachine()
    return {"items": machine.build_for_characters(demo_chars)}



@router.get("/relationship-graph")
async def preview_relationship_graph(title: str = "示例短剧", goal: str = "两人合作却互相试探") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise="一场事故让关系被迫绑定")
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["嘴硬", "聪明"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    return RelationshipGraphBuilder().build(bible, chars, episode)


@router.get("/memory/{batch_task_id}")
async def get_story_memory(batch_task_id: str) -> dict:
    store = AnimationTaskStore(_get_config())
    memory = store.load_batch_memory(batch_task_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Batch memory not found")
    return memory

@router.get("/scene-flow")
async def preview_scene_flow(body_title: str = "示例短剧", goal: str = "关系公开却被打断") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.storyboard_generator import StoryboardGenerator
    from projects.animation.shot_template_library import ShotTemplateLibrary
    from projects.animation.scene_state_flow import SceneStateFlowEngine
    bible = build_story_bible(title=body_title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise="示例")
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["黑色西装"], ["理智"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode, chars, bible.visual_style)
    flow = SceneStateFlowEngine().build(episode)
    return flow

@router.get("/scene-assets")
async def list_animation_scene_assets(
    title: str = "示例短剧",
    genre: str = "都市情感",
    visual_style: str = "high consistency anime cinematic",
    tone: str = "高张力、强反转",
) -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.scene_asset_library import SceneAssetLibrary
    bible = build_story_bible(title=title, genre=genre, format_type="竖屏短剧", target_platform="douyin", visual_style=visual_style, tone=tone, core_premise="示例设定")
    library = SceneAssetLibrary()
    assets = library.build_for_story(bible)
    return {"items": assets, "count": len(assets)}



@router.post("/outline-editor", response_model=AnimationOutlineEditorResponse)
async def animation_outline_editor(body: AnimationOutlineEditorRequest):
    from projects.animation.outline_editor import OutlineEditor
    store = AnimationTaskStore(_get_config())
    previous_memory = store.load_batch_memory(body.batch_parent_id) if body.batch_parent_id else None
    outline = OutlineEditor().build(
        title=body.title,
        premise=body.core_premise,
        episode_goal=body.episode_goal,
        scene_count=body.scene_count,
        previous_memory=previous_memory,
    )
    return AnimationOutlineEditorResponse(outline=outline)


@router.get("/season-memory/{season_id}", response_model=AnimationSeasonMemoryResponse)
async def get_season_memory(season_id: str):
    store = AnimationTaskStore(_get_config())
    memory = store.load_season_memory(season_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Season memory not found")
    return AnimationSeasonMemoryResponse(season_memory=memory)




@router.get("/dialogue-styles")
async def preview_dialogue_styles(title: str = "示例短剧", goal: str = "关系升级却不敢表白") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.dialogue_style_engine import DialogueStyleEngine
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise="关系被外力强行推进")
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    return DialogueStyleEngine().build(bible.to_dict(), [c.to_dict() for c in chars], graph)


@router.get("/season-conflict/{season_id}")
async def get_season_conflict_tree(season_id: str):
    store = AnimationTaskStore(_get_config())
    memory = store.load_season_memory(season_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Season conflict tree not found")
    return {"season_id": season_id, "season_conflict_tree": memory.get("season_conflict_tree", {})}

@router.post("/reference/upload", response_model=AnimationReferenceUploadResponse)
async def upload_animation_reference(
    file: UploadFile = File(...),
    character_name: str = Form(...),
):
    store = AnimationTaskStore(_get_config())
    payload = store.save_reference_asset(character_name=character_name, filename=file.filename or "reference.png", content=await file.read())
    payload["asset_url"] = f"/api/animation/assets/{payload['asset_id']}"
    return AnimationReferenceUploadResponse(**payload)


@router.get("/assets/{asset_id}")
async def get_animation_asset(asset_id: str):
    store = AnimationTaskStore(_get_config())
    path = store.get_asset_path(asset_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Animation asset not found")
    media_type = None
    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
        media_type = f"image/{'jpeg' if suffix in ('.jpg', '.jpeg') else suffix.lstrip('.')}"
    return FileResponse(str(path), media_type=media_type, filename=path.name)




@router.get("/season-trailer-generator")
async def preview_season_trailer_generator(title: str = "示例短剧", goal: str = "终局后还要继续吊观众") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.story_memory_bank import StoryMemoryBank
    from projects.animation.season_memory_bank import SeasonMemoryBank
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.payoff_tracker import PayoffTracker
    from projects.animation.suspense_keeper import SuspenseKeeper
    from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
    from projects.animation.season_suspense_chain import SeasonSuspenseChain
    from projects.animation.finale_payoff_planner import FinalePayoffPlanner
    from projects.animation.season_trailer_generator import SeasonTrailerGenerator
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    relationship_graph = RelationshipGraphBuilder().build(bible, chars, episode)
    memory = StoryMemoryBank().build(bible, chars, episode, relationship_graph, None)
    season_memory = SeasonMemoryBank().build(bible.to_dict(), relationship_graph, episode.to_dict(), None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), relationship_graph, {})
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, relationship_graph)
    payoff_tracker = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    payoff_strength = PayoffStrengthScorer().build(foreshadow, payoff_tracker, climax, relationship_graph)
    chain = SeasonSuspenseChain().build(season_memory, memory, suspense, twists, climax)
    finale = FinalePayoffPlanner().build(chain, payoff_tracker, payoff_strength, {}, season_memory)
    return SeasonTrailerGenerator().build(chain, finale, suspense, payoff_strength)


@router.get("/next-season-hook-planner")
async def preview_next_season_hook_planner(title: str = "示例短剧", goal: str = "终局之后必须引出下季") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.story_memory_bank import StoryMemoryBank
    from projects.animation.season_memory_bank import SeasonMemoryBank
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.payoff_tracker import PayoffTracker
    from projects.animation.suspense_keeper import SuspenseKeeper
    from projects.animation.season_suspense_chain import SeasonSuspenseChain
    from projects.animation.finale_payoff_planner import FinalePayoffPlanner
    from projects.animation.next_season_hook_planner import NextSeasonHookPlanner
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    relationship_graph = RelationshipGraphBuilder().build(bible, chars, episode)
    memory = StoryMemoryBank().build(bible, chars, episode, relationship_graph, None)
    season_memory = SeasonMemoryBank().build(bible.to_dict(), relationship_graph, episode.to_dict(), None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), relationship_graph, {})
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, relationship_graph)
    payoff_tracker = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    chain = SeasonSuspenseChain().build(season_memory, memory, suspense, twists, climax)
    finale = FinalePayoffPlanner().build(chain, payoff_tracker, {}, {}, season_memory)
    return NextSeasonHookPlanner().build(chain, finale, relationship_graph, season_memory)

@router.post("/projects/plan", response_model=AnimationPlanResponse)
async def create_animation_plan(body: AnimationPlanRequest) -> AnimationPlanResponse:
    config = _get_config()
    plan = AnimationRenderPipeline(config)._build_plan(body.model_dump())
    return AnimationPlanResponse(**plan)


@router.post("/projects/consistency-check")
async def animation_consistency_check(body: AnimationPlanRequest) -> dict:
    config = _get_config()
    plan = AnimationRenderPipeline(config)._build_plan(body.model_dump())
    return {
        "consistency_report": plan.get("consistency_report", {}),
        "continuity_report": plan.get("continuity_report", {}),
        "episode_title": plan.get("episode", {}).get("episode_title"),
        "shot_templates": plan.get("shot_templates", []),
        "relationship_graph": plan.get("relationship_graph", {}),
        "story_memory_bank": plan.get("story_memory_bank", {}),
        "dialogue_styles": plan.get("dialogue_styles", {}),
        "season_conflict_tree": plan.get("season_conflict_tree", {}),
        "scene_pacing": plan.get("scene_pacing", {}),
        "climax_plan": plan.get("climax_plan", {}),
        "shot_emotion_filters": plan.get("shot_emotion_filters", {}),
        "foreshadow_plan": plan.get("foreshadow_plan", {}),
        "payoff_tracker": plan.get("payoff_tracker", {}),
    }



@router.post("/projects/scene-pacing")
async def preview_scene_pacing(body: AnimationPlanRequest) -> dict:
    config = _get_config()
    plan = AnimationRenderPipeline(config)._build_plan(body.model_dump())
    return {"scene_pacing": plan.get("scene_pacing", {}), "episode_title": plan.get("episode", {}).get("episode_title")}


@router.post("/projects/climax-plan")
async def preview_climax_plan(body: AnimationPlanRequest) -> dict:
    config = _get_config()
    plan = AnimationRenderPipeline(config)._build_plan(body.model_dump())
    return {"climax_plan": plan.get("climax_plan", {}), "episode_title": plan.get("episode", {}).get("episode_title")}


@router.post("/projects/render", response_model=AnimationRenderResponse)
async def render_animation_project(body: AnimationPlanRequest) -> AnimationRenderResponse:
    config = _get_config()
    store = AnimationTaskStore(config)
    initial = store.create({"stage_message": "动画剧任务已入队，请等待规划与渲染。"})
    asyncio.create_task(AnimationRenderPipeline(config).run(initial.task_id, body.model_dump()))
    return AnimationRenderResponse(
        task_id=initial.task_id,
        status=initial.status,
        stage=initial.stage,
        stage_message=initial.stage_message,
        task_dir=initial.task_dir,
    )


@router.post("/projects/render-batch", response_model=AnimationBatchRenderResponse)
async def render_animation_batch(body: AnimationBatchRenderRequest) -> AnimationBatchRenderResponse:
    config = _get_config()
    store = AnimationTaskStore(config)
    batch = store.create({
        "stage_message": "批量动画任务已入队。",
        "stage": "batch_queued",
        "batch_children": [],
    })
    child_ids = []
    for idx, goal in enumerate(body.episode_goals, start=1):
        request_dict = body.model_dump(exclude={"episode_goals", "title_prefix"})
        request_dict["episode_goal"] = goal
        prefix = (body.title_prefix or body.title).strip()
        request_dict["title"] = f"{prefix} - EP{idx:02d}"
        request_dict["batch_parent_id"] = batch.task_id
        request_dict["episode_index"] = idx
        request_dict["reuse_assets_across_episodes"] = True
        child = store.create({
            "stage_message": f"批量子任务 EP{idx:02d} 已入队。",
            "batch_parent_id": batch.task_id,
        })
        child_ids.append(child.task_id)
        asyncio.create_task(AnimationRenderPipeline(config).run(child.task_id, request_dict))
    store.update(
        batch.task_id,
        status="processing",
        stage="batch_started",
        stage_message=f"已创建 {len(child_ids)} 个批量子任务。",
        progress=5,
        batch_children=child_ids,
    )
    return AnimationBatchRenderResponse(
        batch_task_id=batch.task_id,
        task_ids=child_ids,
        status="processing",
        stage="batch_started",
        stage_message=f"已创建 {len(child_ids)} 个批量子任务。",
    )


@router.post("/shots/retry", response_model=AnimationTaskResponse)
async def retry_animation_shot(body: AnimationShotRetryRequest) -> AnimationTaskResponse:
    config = _get_config()
    task = await AnimationRenderPipeline(config).retry_shot(body.task_id, body.shot_id)
    return AnimationTaskResponse(**task)




@router.get("/batch-assets/{batch_task_id}")
async def get_animation_batch_assets(batch_task_id: str) -> dict:
    store = AnimationTaskStore(_get_config())
    path = store.batch_cache_path(batch_task_id)
    if not path.exists():
        return {"batch_task_id": batch_task_id, "reusable_assets": [], "episodes": []}
    return json.loads(path.read_text(encoding="utf-8"))



@router.get("/scene-twists")
async def preview_scene_twists(title: str = "示例短剧", goal: str = "突发真相曝光") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.scene_twist_detector import SceneTwistDetector
    story = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色西装裙"], personality=["理智"], voice_style="冷静", catchphrases=["你最好想清楚再说。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["白衬衫"], personality=["嘴硬"], voice_style="自然", catchphrases=["这戏我接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal=goal, scene_count=4)
    return SceneTwistDetector().build(episode.to_dict())


@router.get("/highlight-shots")
async def preview_highlight_shots(title: str = "示例短剧", goal: str = "公开场合身份反转") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.storyboard_generator import StoryboardGenerator
    from projects.animation.shot_template_library import ShotTemplateLibrary
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.highlight_shot_orchestrator import HighlightShotOrchestrator
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    story = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色西装裙"], personality=["理智"], voice_style="冷静", catchphrases=["你最好想清楚再说。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["白衬衫"], personality=["嘴硬"], voice_style="自然", catchphrases=["这戏我接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal=goal, scene_count=4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode=episode, characters=chars, visual_style=story.visual_style)
    relationship_graph = RelationshipGraphBuilder().build(story, chars, episode)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), relationship_graph, {"core_conflict": goal})
    return HighlightShotOrchestrator().build(episode.to_dict(), twists, climax)



@router.get("/shot-emotion-filters")
async def preview_shot_emotion_filters(title: str = "示例短剧", goal: str = "当众摊牌前气氛持续升温") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.character_emotion_arc_engine import CharacterEmotionArcEngine
    from projects.animation.shot_emotion_filter import ShotEmotionFilter
    story = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色西装裙"], personality=["理智"], voice_style="冷静", catchphrases=["你最好想清楚再说。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["白衬衫"], personality=["嘴硬"], voice_style="自然", catchphrases=["这戏我接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal=goal, scene_count=4)
    arcs = CharacterEmotionArcEngine().build(episode.to_dict(), [c.to_dict() for c in chars])
    return ShotEmotionFilter().build(episode.to_dict(), arcs)


@router.get("/foreshadow-plan")
async def preview_foreshadow_plan(title: str = "示例短剧", goal: str = "反转前先埋下道具与对白线索") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    story = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色西装裙"], personality=["理智"], voice_style="冷静", catchphrases=["你最好想清楚再说。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["白衬衫"], personality=["嘴硬"], voice_style="自然", catchphrases=["这戏我接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal=goal, scene_count=4)
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    twists = SceneTwistDetector().build(episode.to_dict())
    return ForeshadowPlanter().build(episode.to_dict(), twists, graph)


@router.get("/payoff-tracker")
async def preview_payoff_tracker(title: str = "示例短剧", goal: str = "用前面线索在高潮处完成回收") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.payoff_tracker import PayoffTracker
    story = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible(name="沈晚", role="女主", age_range="23-28", appearance=["黑长发"], wardrobe=["黑色西装裙"], personality=["理智"], voice_style="冷静", catchphrases=["你最好想清楚再说。"]),
        build_character_bible(name="周叙", role="男主", age_range="25-30", appearance=["短黑发"], wardrobe=["白衬衫"], personality=["嘴硬"], voice_style="自然", catchphrases=["这戏我接了。"]),
    ]
    episode = EpisodeWriter().create_episode_outline(story_bible=story, characters=chars, episode_goal=goal, scene_count=4)
    graph = RelationshipGraphBuilder().build(story, chars, episode)
    twists = SceneTwistDetector().build(episode.to_dict())
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, graph)
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, {"core_conflict": goal})
    return PayoffTracker().build(foreshadow, twists, climax)


@router.get("/tasks", response_model=AnimationTaskListResponse)
async def list_animation_tasks(limit: int = 20) -> AnimationTaskListResponse:
    store = AnimationTaskStore(_get_config())
    items = [AnimationTaskResponse(**item) for item in store.list_recent(limit=limit)]
    return AnimationTaskListResponse(items=items)


@router.get("/tasks/{task_id}", response_model=AnimationTaskResponse)
async def get_animation_task(task_id: str) -> AnimationTaskResponse:
    store = AnimationTaskStore(_get_config())
    task = store.load(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Animation task not found")
    if task.get("batch_children"):
        child_states = []
        for child_id in task.get("batch_children", []):
            child = store.load(child_id)
            if child:
                child_states.append({"task_id": child_id, "status": child.get("status"), "stage": child.get("stage"), "progress": child.get("progress", 0)})
        task = dict(task)
        task.setdefault("artifacts", {})
        task["artifacts"]["batch_children_json"] = json.dumps(child_states, ensure_ascii=False)
    return AnimationTaskResponse(**task)


@router.get("/tasks/{task_id}/artifact/{artifact_key}")
async def get_animation_task_artifact(task_id: str, artifact_key: str):
    store = AnimationTaskStore(_get_config())
    task = store.load(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Animation task not found")
    artifacts = task.get("artifacts", {})
    file_path = artifacts.get(artifact_key)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_key}")
    file_path = Path(file_path)
    if not file_path.is_absolute():
        file_path = store.path(task_id) / file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_key}")
    media_type = None
    suffix = Path(file_path).suffix.lower()
    if suffix == ".mp4":
        media_type = "video/mp4"
    elif suffix == ".srt":
        media_type = "application/x-subrip"
    elif suffix == ".json":
        media_type = "application/json"
    return FileResponse(str(file_path), media_type=media_type, filename=file_path.name)



@router.get("/season-suspense-chain")
async def preview_season_suspense_chain(title: str = "示例短剧", goal: str = "线索跨集延迟兑现") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.story_memory_bank import StoryMemoryBank
    from projects.animation.season_memory_bank import SeasonMemoryBank
    from projects.animation.suspense_keeper import SuspenseKeeper
    from projects.animation.season_suspense_chain import SeasonSuspenseChain
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    story_memory = StoryMemoryBank().build(bible, chars, episode, graph, previous_memory=None, episode_index=1)
    season_memory = SeasonMemoryBank().build(bible.to_dict(), graph, episode.to_dict(), None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, {"core_conflict": "真相与情感双冲突"})
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, graph)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    return SeasonSuspenseChain().build(season_memory, story_memory, suspense, twists, climax, "preview_batch")


@router.get("/finale-payoff-plan")
async def preview_finale_payoff_plan(title: str = "示例短剧", goal: str = "终局集需要多线回收") -> dict:
    from projects.animation.story_bible import build_story_bible
    from projects.animation.character_bible import build_character_bible
    from projects.animation.episode_writer import EpisodeWriter
    from projects.animation.relationship_graph import RelationshipGraphBuilder
    from projects.animation.scene_twist_detector import SceneTwistDetector
    from projects.animation.climax_orchestrator import ClimaxOrchestrator
    from projects.animation.foreshadow_planter import ForeshadowPlanter
    from projects.animation.story_memory_bank import StoryMemoryBank
    from projects.animation.season_memory_bank import SeasonMemoryBank
    from projects.animation.season_conflict_tree import SeasonConflictTree
    from projects.animation.payoff_tracker import PayoffTracker
    from projects.animation.suspense_keeper import SuspenseKeeper
    from projects.animation.payoff_strength_scorer import PayoffStrengthScorer
    from projects.animation.season_suspense_chain import SeasonSuspenseChain
    from projects.animation.finale_payoff_planner import FinalePayoffPlanner
    bible = build_story_bible(title=title, genre="都市情感", format_type="竖屏短剧", target_platform="douyin", visual_style="high consistency anime cinematic", tone="高张力", core_premise=goal)
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["西装裙"], ["理智", "强势"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明", "嘴硬"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, goal, 4)
    graph = RelationshipGraphBuilder().build(bible, chars, episode)
    story_memory = StoryMemoryBank().build(bible, chars, episode, graph, previous_memory=None, episode_index=1)
    season_memory = SeasonMemoryBank().build(bible.to_dict(), graph, episode.to_dict(), None)
    conflict = SeasonConflictTree().build(bible.to_dict(), graph, story_memory, None)
    twists = SceneTwistDetector().build(episode.to_dict())
    climax = ClimaxOrchestrator().build(episode.to_dict(), graph, conflict)
    foreshadow = ForeshadowPlanter().build(episode.to_dict(), twists, graph)
    tracker = PayoffTracker().build(foreshadow, twists, climax)
    suspense = SuspenseKeeper().build(episode.to_dict(), twists, foreshadow, climax)
    chain = SeasonSuspenseChain().build(season_memory, story_memory, suspense, twists, climax, "preview_batch")
    strength = PayoffStrengthScorer().build(foreshadow, tracker, climax, graph)
    return FinalePayoffPlanner().build(chain, tracker, strength, conflict, season_memory)
