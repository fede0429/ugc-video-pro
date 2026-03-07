
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json, tempfile
from pathlib import Path
from core.platform_publish_adapter import PlatformPublishAdapter
from core.publish_queue import PublishQueue

def main():
    with tempfile.TemporaryDirectory() as td:
        config = {"web": {"video_dir": td}}
        adapter = PlatformPublishAdapter()
        payload = adapter.build_payload(
            platform="douyin",
            publish_package={
                "short_title": "新品测评",
                "description": "真实测评短视频",
                "hashtags": ["#好物推荐", "#真实测评"],
                "caption_options": ["这条视频给你讲明白"],
                "platform_notes": {"recommended_cover_text": "三天实测"},
            },
            final_video_path="/tmp/final.mp4",
            subtitle_path="/tmp/final.srt",
            task_id="ugc-test",
        )
        queue = PublishQueue(config)
        entry = queue.enqueue(task_id="ugc-test", platform="douyin", payload=payload.to_dict())
        items = queue.list()
        assert items and items[0]["task_id"] == "ugc-test"
        assert entry["payload"]["platform"] == "douyin"
        print(json.dumps({"queue_size": len(items), "cover_text": payload.cover_text}, ensure_ascii=False))

if __name__ == "__main__":
    main()
