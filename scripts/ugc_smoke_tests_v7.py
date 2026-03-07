from __future__ import annotations
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.platform_publish_adapter import PlatformPublishAdapter
from core.publish_queue import PublishQueue
from core.platform_resource_center import PlatformResourceCenter
from core.publish_retry_engine import PublishRetryEngine

def main():
    with tempfile.TemporaryDirectory() as td:
        config = {"web": {"video_dir": td}}
        payload = PlatformPublishAdapter().build_payload(
            platform="douyin",
            publish_package={
                "short_title": "发布失败重试测试",
                "description": "资源中心与重试器",
                "hashtags": ["#ugc"],
                "caption_options": ["看完这一条再决定"],
            },
            final_video_path="/tmp/final.mp4",
            subtitle_path="/tmp/final.srt",
            task_id="ugc-v12",
        )
        center = PlatformResourceCenter(config)
        bundle = center.build_resource_bundle("douyin", payload.to_dict())
        queue = PublishQueue(config)
        entry = queue.enqueue(task_id="ugc-v12", platform="douyin", payload=payload.to_dict())
        queue.update_status(entry["queue_id"], status="failed_publish", extra={"last_error": "mock remote failure"})
        retried = PublishRetryEngine(config).retry(entry["queue_id"], dry_run=True, note="smoke retry")
        assert bundle["platform"] == "douyin"
        assert retried["queue"]["status"] == "retry_prepared"
        assert retried["attempt"]["response"]["ready"] is True
        print(json.dumps({"queue_id": entry["queue_id"], "retry_count": retried["queue"]["retry_count"], "default_hashtags": bundle["default_hashtags"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
