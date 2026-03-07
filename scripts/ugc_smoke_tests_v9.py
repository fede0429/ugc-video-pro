from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
from core.platform_credential_center import PlatformCredentialCenter
from core.publish_queue import PublishQueue
from core.publish_task_executor import PublishTaskExecutor
from core.platform_receipt_recorder import PlatformReceiptRecorder

def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        config = {"web": {"video_dir": td}}
        PlatformCredentialCenter(config).update_platform("douyin", {
            "client_id": "cid-demo",
            "client_secret": "secret-demo",
            "access_token": "token-demo-123456",
            "account_label": "studio-main",
        })
        queue = PublishQueue(config)
        entry = queue.enqueue(
            task_id="ugc-task-14",
            platform="douyin",
            payload={"title": "Demo publish", "hashtags": ["#种草"]},
            review_state="approved",
        )
        result = PublishTaskExecutor(config).execute(entry["queue_id"], dry_run=True, actor="smoke-test")
        assert result["queue_entry"]["status"] == "published_dry_run"
        receipts = PlatformReceiptRecorder(config).list(task_id="ugc-task-14")
        assert receipts and receipts[0]["queue_id"] == entry["queue_id"]
        print("UGC v14 smoke test passed", receipts[0]["status"])

if __name__ == "__main__":
    main()
