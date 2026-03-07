from __future__ import annotations
import asyncio, json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projects.animation.render_pipeline import AnimationRenderPipeline
from projects.animation.task_store import AnimationTaskStore
from web.schemas_animation import AnimationPlanRequest
from projects.animation.outline_editor import OutlineEditor
from projects.animation.season_memory_bank import SeasonMemoryBank


def make_config(root: str) -> dict:
    return {
        "web": {"video_dir": root},
        "video": {"output_dir": root, "video_codec": "libx264", "audio_codec": "aac", "crf": 23, "preset": "fast"},
        "tts": {"model": "quality", "voices": {}},
        "kie": {"api_key": "DUMMY"},
    }


async def main():
    temp_root = tempfile.mkdtemp(prefix="animation_smoke_v2_")
    config = make_config(temp_root)
    pipeline = AnimationRenderPipeline(config)
    store = AnimationTaskStore(config)
    req = AnimationPlanRequest(
        title="测试动画剧",
        genre="都市情感",
        format_type="竖屏短剧",
        target_platform="douyin",
        visual_style="high consistency anime cinematic",
        tone="高张力",
        core_premise="男女主因为一场事故被迫绑定。",
        episode_goal="第一次公开亮相却失控",
        scene_count=4,
        characters=[{
            "name": "沈晚","role":"女主","age_range":"23-28","appearance":["黑长发"],"wardrobe":["西装裙"],"personality":["理智"],"voice_style":"冷静","catchphrases":["你最好想清楚再说。"],"reference_image_url":""
        }],
        language="zh",
        aspect_ratio="9:16",
        dry_run=True,
    ).model_dump()
    task = store.create()
    plan = pipeline._build_plan(req)
    assert "outline_editor" in plan
    assert "season_memory_bank" in plan
    result = await pipeline.run(task.task_id, req)
    assert result["status"] == "completed"
    p = Path(store.path(task.task_id))/"planning"/"season_memory_bank.json"
    assert p.exists()
    season = json.loads(p.read_text(encoding="utf-8"))
    assert season["season_id"]
    outline = OutlineEditor().build("A","B","C",4)
    merged = SeasonMemoryBank().merge_into_batch(None, season)
    assert outline["beats"]
    assert merged["season_arcs"]
    print(json.dumps({"ok": True, "season_id": season["season_id"], "open_loops": season["open_loops"][:2], "beat_count": len(outline["beats"])}, ensure_ascii=False, indent=2))
    shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(main())
