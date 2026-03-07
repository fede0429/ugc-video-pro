from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
from core.platform_credential_center import PlatformCredentialCenter
from core.publish_queue import PublishQueue


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        config = {"web": {"video_dir": td}}
        creds = PlatformCredentialCenter(config)
        creds.update_platform("douyin", {
            "client_id": "cid-demo",
            "client_secret": "secret-demo",
            "access_token": "token-demo-123456",
            "account_label": "studio-main",
        })
        masked = creds.get_platform("douyin", masked=True)
        assert masked["client_secret"].startswith("secr") or "*" in masked["client_secret"]
        auth = creds.build_publish_auth_context("douyin")
        assert auth["has_credentials"] is True

        queue = PublishQueue(config)
        entry = queue.enqueue(
            task_id="ugc-task-1",
            platform="douyin",
            payload={"title": "Demo publish"},
            scheduled_at=1735689600.0,
            review_state="approved",
        )
        assert entry["status"] == "scheduled"
        due = queue.list_due(now_ts=1735689601.0)
        assert due and due[0]["queue_id"] == entry["queue_id"]
        rescheduled = queue.reschedule(entry["queue_id"], 1735693200.0, note="manual adjust")
        assert rescheduled and rescheduled["scheduled_at"] == 1735693200.0
        print("UGC v13 smoke test passed")


if __name__ == "__main__":
    main()
