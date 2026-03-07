
from __future__ import annotations
import asyncio, json
from core.script_generator import ScriptGenerator
from core.timeline_types import UGCVideoRequest, ProductProfile, PresenterProfile
from core.director_agent import ProductionPlan
from services.video_scoring_service import VideoScoringService

async def main():
    config = {"video": {}}
    sg = ScriptGenerator(config)
    req = UGCVideoRequest(task_id="ugc-smoke", user_id="user-1", mode="image_to_video", model="seedance_15", duration=20, language="zh", platform="tiktok")
    prod = ProductProfile(product_type="护肤精华", brand="TestBrand", description="修护精华液", key_features=["修护", "保湿"], selling_points=["吸收快", "不搓泥"], consistency_anchors=["蓝色瓶身", "滴管头"])
    pres = PresenterProfile(persona_template="review_blogger", voice_preset="female", style_notes="natural")
    plan = ProductionPlan(
        strategy="testimonial_demo_hybrid",
        video_model="seedance_15",
        platform="tiktok",
        persona="review_blogger",
        hook_style="pain_point",
        tone_style="natural",
        cta_style="soft",
        primary_language="zh",
        total_duration=20,
        a_roll_ratio=0.45,
        b_roll_ratio=0.55,
        estimated_cost_usd=0.2,
        segments_json=[
            {"track_type": "a_roll", "duration_seconds": 4, "spoken_line": "以前我的皮肤特别容易干。", "overlay_text": "干皮救星", "scene_purpose": "hook"},
            {"track_type": "b_roll", "duration_seconds": 5, "overlay_text": "给你看质地", "scene_purpose": "proof", "product_action": "texture demo"},
            {"track_type": "b_roll", "duration_seconds": 5, "overlay_text": "上脸吸收很快", "scene_purpose": "demo", "product_action": "hands on"},
            {"track_type": "a_roll", "duration_seconds": 6, "spoken_line": "如果你也在找一款修护型精华，这支真的可以试试。", "overlay_text": "真的会回购", "scene_purpose": "cta"},
        ],
        selected_framework="pas",
        selected_variant_id="v1",
        variants=[],
        reasoning=[],
    )
    timeline = await sg.generate_timeline(req, prod, pres, production_plan=plan)
    score = VideoScoringService().score(timeline, None)
    assert len(timeline.segments) == 4
    assert timeline.segments[1].track_type == "b_roll"
    assert timeline.segments[1].shot_type
    assert timeline.segments[1].camera_movement
    assert score.total_score > 0
    print(json.dumps({
        "ok": True,
        "segment_count": len(timeline.segments),
        "broll_shot_type": timeline.segments[1].shot_type,
        "broll_camera": timeline.segments[1].camera_movement,
        "creative_score": score.total_score,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
