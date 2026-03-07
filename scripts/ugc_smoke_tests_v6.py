
from __future__ import annotations
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.platform_publish_adapter import PlatformPublishAdapter
from core.publish_queue import PublishQueue
from core.review_state_machine import ReviewStateMachine
from core.direct_publish_skeleton import DirectPublishSkeleton


def main():
    with tempfile.TemporaryDirectory() as td:
        config = {"web": {"video_dir": td}}
        payload = PlatformPublishAdapter().build_payload(
            platform="tiktok",
            publish_package={
                "short_title": "爆款钩子测试",
                "description": "真实口播带货",
                "hashtags": ["#ugc", "#test"],
                "caption_options": ["先看这3秒"],
                "platform_notes": {"recommended_cover_text": "先别划走"},
            },
            final_video_path="/tmp/final.mp4",
            subtitle_path="/tmp/final.srt",
            task_id="ugc-v11",
        )
        queue = PublishQueue(config)
        entry = queue.enqueue(task_id="ugc-v11", platform="tiktok", payload=payload.to_dict())
        review = ReviewStateMachine().transition({}, new_status="draft", actor="system", note="init")
        review = ReviewStateMachine().transition(review, new_status="in_review", actor="qa", note="check")
        review = ReviewStateMachine().transition(review, new_status="approved", actor="qa", note="ok")
        attempt = DirectPublishSkeleton().build_attempt(
            task_id="ugc-v11",
            platform="tiktok",
            publish_payload=payload.to_dict(),
            dry_run=True,
        )
        assert entry["task_id"] == "ugc-v11"
        assert review["status"] == "approved"
        assert attempt.response["ready"] is True
        print(json.dumps({"queue_id": entry["queue_id"], "review_status": review["status"], "transport": attempt.response["transport"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
