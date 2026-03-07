from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.variant_generator import VariantGenerator
from core.hook_score_engine import HookScoreEngine
from core.multi_script_engine import MultiScriptBatchEngine
from core.director_agent import ProductionPlan
from core.script_generator import ScriptGenerator
from core.timeline_types import ProductProfile, PresenterProfile
from projects.animation.scene_state_flow import SceneStateFlowEngine
from projects.animation.episode_asset_reuse import EpisodeAssetReusePlanner
from projects.animation.story_bible import build_story_bible
from projects.animation.character_bible import build_character_bible
from projects.animation.episode_writer import EpisodeWriter
from projects.animation.storyboard_generator import StoryboardGenerator
from projects.animation.shot_template_library import ShotTemplateLibrary

async def main():
    vg = VariantGenerator()
    variants = vg.build_batch_variants(
        language="zh",
        product_name="TestBrand 修护精华",
        selling_points=["吸收快", "不搓泥", "修护泛红"],
        preferred_styles=["pain_point", "confession_hook"],
        max_variants=6,
    )
    assert len(variants) == 6
    assert variants[0].hook_score["total_score"] >= variants[-1].hook_score["total_score"]
    hs = HookScoreEngine().score(variants[0].hook_line, variants[0].hook_style, "zh", "TestBrand 修护精华")
    assert hs.total_score > 0

    production_plan = ProductionPlan(
        strategy="testimonial_demo_hybrid",
        video_model="seedance_15",
        platform="douyin",
        persona="review_blogger",
        hook_style=variants[0].hook_style,
        tone_style="authentic_friend",
        cta_style="link_in_bio",
        primary_language="zh",
        total_duration=24,
        a_roll_ratio=0.42,
        b_roll_ratio=0.58,
        estimated_cost_usd=0.12,
        segments_json=[
            {"id": "seg_01", "track": "a_roll", "duration": 5, "spoken_line": variants[0].hook_line, "overlay_text": "先看结果", "scene_purpose": "hook"},
            {"id": "seg_02", "track": "b_roll", "duration": 7, "visual_goal": "problem", "product_action": "usage_demo", "overlay_text": "吸收快", "scene_purpose": "problem"},
            {"id": "seg_03", "track": "a_roll", "duration": 6, "spoken_line": "我最在意的是不搓泥，而且修护真的快。", "overlay_text": "不搓泥", "scene_purpose": "proof"},
            {"id": "seg_04", "track": "b_roll", "duration": 6, "visual_goal": "cta", "product_action": "packshot", "overlay_text": "现在试试", "scene_purpose": "cta"},
        ],
        selected_framework="pas",
        selected_variant_id=variants[0].variant_id,
        variants=[v.to_dict() for v in variants[:4]],
        reasoning=["smoke_test"],
    )

    class DummyReq:
        task_id = "smoke"
        duration = 24
        language = "zh"
        platform = "douyin"
        batch_variants = 4
        script_batch_size = 3

    product_profile = ProductProfile(product_type="serum", description="修护精华", selling_points=["吸收快", "不搓泥", "修护泛红"])
    presenter_profile = PresenterProfile(persona_template="review_blogger", style_notes="自然测评")
    batch = await MultiScriptBatchEngine(ScriptGenerator({"gemini": {}})).generate(DummyReq(), product_profile, presenter_profile, production_plan, max_scripts=3)
    assert batch["selected_variant_id"]
    assert len(batch["candidates"]) >= 3

    bible = build_story_bible("测试短剧", "都市情感", "竖屏短剧", "douyin", "high consistency anime cinematic", "高张力", "直播事故让两人绑定关系")
    chars = [
        build_character_bible("沈晚", "女主", "23-28", ["黑长发"], ["黑色西装裙"], ["理智"], "冷静"),
        build_character_bible("周叙", "男主", "25-30", ["短黑发"], ["白衬衫"], ["聪明"], "自然"),
    ]
    episode = EpisodeWriter().create_episode_outline(bible, chars, "公开亮相却被旧情人打断", 4)
    episode = StoryboardGenerator(template_library=ShotTemplateLibrary()).build_shots(episode, chars, bible.visual_style)
    flow = SceneStateFlowEngine().build(episode)
    reuse = EpisodeAssetReusePlanner().build(bible, chars, episode, batch_parent_id=None)
    assert flow["scene_count"] == 4
    assert len(flow["transitions"]) == 3
    assert reuse["reusable_assets"]
    print(json.dumps({
        "ok": True,
        "top_variant": variants[0].hook_line,
        "top_hook_score": variants[0].hook_score["total_score"],
        "transition_count": len(flow["transitions"]),
        "reuse_asset_count": len(reuse["reusable_assets"]),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
