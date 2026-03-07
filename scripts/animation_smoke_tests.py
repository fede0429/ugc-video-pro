
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
import shutil
import tempfile

from projects.animation.render_pipeline import AnimationRenderPipeline
from projects.animation.task_store import AnimationTaskStore
from web.schemas_animation import AnimationPlanRequest


def make_config(root: str) -> dict:
    return {
        "web": {"video_dir": root},
        "video": {"output_dir": root, "video_codec": "libx264", "audio_codec": "aac", "crf": 23, "preset": "fast"},
        "tts": {"model": "quality", "voices": {}},
        "kie": {"api_key": "DUMMY"},
    }


def sample_request() -> dict:
    return AnimationPlanRequest(
        title="测试动画剧",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力、强反转",
        core_premise="两位主角因为直播事故被迫绑定关系。",
        episode_goal="第一次公开亮相，却因旧情人出现而失控。",
        scene_count=3,
        characters=[
            {
                "name": "沈晚",
                "role": "女主",
                "age_range": "23-28",
                "appearance": ["黑长发", "冷白皮"],
                "wardrobe": ["西装裙"],
                "personality": ["理智", "克制"],
                "voice_style": "冷静",
                "catchphrases": ["你最好想清楚再说。"],
                "reference_image_url": "",
            },
            {
                "name": "周叙",
                "role": "男主",
                "age_range": "25-30",
                "appearance": ["短黑发"],
                "wardrobe": ["白衬衫"],
                "personality": ["聪明", "嘴硬"],
                "voice_style": "自然",
                "catchphrases": ["这戏我还真接了。"],
                "reference_image_url": "",
            },
        ],
        language="zh",
        aspect_ratio="9:16",
        model_variant="seedance_2",
        fallback_model="seedance_15",
        enable_tts=False,
        dry_run=True,
        shot_retry_limit=2,
    ).model_dump()


async def main():
    temp_root = tempfile.mkdtemp(prefix="animation_smoke_")
    config = make_config(temp_root)
    pipeline = AnimationRenderPipeline(config)
    store = AnimationTaskStore(config)

    request = sample_request()
    created = store.create(initial={"stage_message": "created by smoke test"})

    plan = pipeline._build_plan(request)
    assert plan["story_bible"]["title"] == "测试动画剧"
    assert plan["continuity_report"]["shot_count"] >= 9
    assert "character_states" in plan
    assert "scene_assets" in plan
    assert "scene_state_flow" in plan
    assert "episode_asset_reuse" in plan
    assert "relationship_graph" in plan
    assert "story_memory_bank" in plan

    result = await pipeline.run(created.task_id, request)
    assert result["status"] == "completed"
    assert result["stage"] in ("dry_run", "dry_run_complete")

    asset = store.save_reference_asset("沈晚", "shenwan.png", b"fakeimage")
    assert Path(asset["local_path"]).exists()

    plan_file = Path(store.path(created.task_id)) / "planning" / "animation_plan.json"
    payload = json.loads(plan_file.read_text(encoding="utf-8"))
    assert "consistency_report" in payload
    assert "shot_templates" in payload and payload["shot_templates"]
    assert "character_states" in payload
    assert "scene_assets" in payload
    assert "scene_state_flow" in payload
    assert "episode_asset_reuse" in payload

    print(json.dumps({
        "ok": True,
        "task_id": created.task_id,
        "shot_count": plan["continuity_report"]["shot_count"],
        "consistency_score": payload["consistency_report"]["consistency_score"],
        "template_count": len(payload["shot_templates"]),
        "character_state_count": len(payload["character_states"]),
        "scene_asset_count": len(payload["scene_assets"].get("library", [])),
        "transition_count": len(payload["scene_state_flow"].get("transitions", [])),
        "reuse_asset_count": len(payload["episode_asset_reuse"].get("reusable_assets", [])),
        "asset_id": asset["asset_id"],
        "temp_root": temp_root,
    }, ensure_ascii=False, indent=2))

    shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
