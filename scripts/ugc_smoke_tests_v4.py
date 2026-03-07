from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.publish_prep_service import PublishPrepService
from core.asset_reuse_pool import AssetReusePool
from core.director_agent import ProductionPlan
from core.timeline_types import TimelineScript, TimelineSegment, ProductProfile, PresenterProfile


class DummyReq:
    language = "zh"
    platform = "douyin"
    brand_name = "TestBrand"


def main():
    timeline = TimelineScript(
        task_id="smoke_v4",
        language="zh",
        segments=[
            TimelineSegment(segment_id="s1", segment_index=1, track_type="a_roll", duration_seconds=5, spoken_line="这个修护精华真让我改观了", overlay_text="先看结果"),
            TimelineSegment(segment_id="s2", segment_index=2, track_type="b_roll", duration_seconds=5, overlay_text="吸收很快", b_roll_prompt="macro hand demo"),
            TimelineSegment(segment_id="s3", segment_index=3, track_type="a_roll", duration_seconds=5, spoken_line="不搓泥，泛红也稳得快。", overlay_text="不搓泥"),
            TimelineSegment(segment_id="s4", segment_index=4, track_type="b_roll", duration_seconds=5, overlay_text="点这里看更多", b_roll_prompt="packshot"),
        ],
    )
    product = ProductProfile(brand="TestBrand", description="修护精华", selling_points=["吸收快", "不搓泥", "修护泛红"])
    presenter = PresenterProfile(persona_template="review_blogger", style_notes="自然")
    plan = ProductionPlan(strategy="testimonial", video_model="seedance_15", platform="douyin", persona="review_blogger", hook_style="result_first", tone_style="authentic", cta_style="link_in_bio", primary_language="zh", total_duration=20, a_roll_ratio=0.4, b_roll_ratio=0.6, estimated_cost_usd=0.1, segments_json=[])
    pkg = PublishPrepService().build(request=DummyReq(), product_profile=product, presenter_profile=presenter, production_plan=plan, timeline=timeline, final_video_path="/tmp/final.mp4")
    assert pkg.title and pkg.hashtags and pkg.reusable_assets
    cfg = {"web": {"video_dir": tempfile.mkdtemp(prefix="ugc_pool_")}}
    pool = AssetReusePool(cfg)
    entry = pool.save_entry(request=DummyReq(), product_profile=product, payload={"hook_lines": [pkg.hook_line], "reusable_assets": pkg.reusable_assets, "publish_package": pkg.to_dict()})
    summary = pool.summarize(request=DummyReq(), product_profile=product)
    assert entry["entry_id"]
    assert summary["entry_count"] >= 1
    print(json.dumps({"ok": True, "title": pkg.title, "hashtags": pkg.hashtags[:4], "entry_count": summary["entry_count"]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
