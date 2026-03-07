#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # type: ignore

from main import load_config
from web.app import create_app


SAMPLE_PAYLOAD = {
    "title": "《失控合约》",
    "genre": "都市情感",
    "format_type": "竖屏短剧",
    "target_platform": "douyin",
    "visual_style": "high consistency anime cinematic, vertical short drama, rich facial acting",
    "tone": "高张力、强反转",
    "core_premise": "失业编剧被迫替豪门千金伪装未婚夫，两人在直播事故后卷入家族秘密。",
    "episode_goal": "伪装关系第一次公开亮相，却因为旧情人出现而失控",
    "scene_count": 4,
    "language": "zh",
    "aspect_ratio": "9:16",
    "model_variant": "seedance_2",
    "fallback_model": "seedance_15",
    "enable_tts": False,
    "dry_run": True,
    "shot_retry_limit": 1,
    "characters": [
        {
            "name": "沈晚",
            "role": "豪门千金 / 女主",
            "age_range": "23-28",
            "appearance": ["黑长发", "冷白皮", "精致五官"],
            "wardrobe": ["黑色修身西装裙", "银色耳饰"],
            "personality": ["理智", "强势", "克制"],
            "voice_style": "冷静、锋利、克制",
            "catchphrases": ["你最好想清楚再说。"],
            "reference_image_url": "",
        },
        {
            "name": "周叙",
            "role": "失业编剧 / 男主",
            "age_range": "25-30",
            "appearance": ["短黑发", "干净轮廓", "略显疲惫"],
            "wardrobe": ["白衬衫", "深色长裤"],
            "personality": ["聪明", "嘴硬", "有韧劲"],
            "voice_style": "年轻、自然、有一点不服输",
            "catchphrases": ["这戏我还真接了。"],
            "reference_image_url": "",
        },
    ],
}


def assert_status(resp, expected=200, label="request"):
    if resp.status_code != expected:
        raise AssertionError(f"{label} failed: {resp.status_code} {resp.text[:400]}")


def poll_task(client: TestClient, task_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/animation/tasks/{task_id}")
        assert_status(resp, 200, "poll task")
        data = resp.json()
        last = data
        if data.get("status") in {"completed", "failed"}:
            return data
        time.sleep(0.2)
    return last or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Animation Studio API smoke test using FastAPI TestClient.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    temp_root = tempfile.mkdtemp(prefix="animation_api_smoke_")
    os.environ["DATA_ROOT"] = temp_root

    config = load_config(args.config)
    app = create_app(config)
    summary: dict[str, object] = {}
    with TestClient(app) as client:
        # health
        resp = client.get("/api/animation/health")
        assert_status(resp, 200, "health")
        summary["health"] = resp.json().get("status")

        # preview endpoints
        preview_paths = [
            "/api/animation/templates",
            "/api/animation/states",
            "/api/animation/scene-assets",
            "/api/animation/scene-twists",
            "/api/animation/highlight-shots",
            "/api/animation/emotion-arcs",
            "/api/animation/punchline-dialogue",
            "/api/animation/shot-emotion-filters",
            "/api/animation/foreshadow-plan",
            "/api/animation/payoff-tracker",
            "/api/animation/suspense-keeper",
            "/api/animation/payoff-strength",
            "/api/animation/season-suspense-chain",
            "/api/animation/finale-payoff-plan",
            "/api/animation/season-trailer-generator",
            "/api/animation/next-season-hook-planner",
        ]
        preview_ok = 0
        for path in preview_paths:
            resp = client.get(path)
            assert_status(resp, 200, path)
            preview_ok += 1
        summary["preview_ok"] = preview_ok

        # plan endpoints
        for path, key in [
            ("/api/animation/projects/plan", "plan"),
            ("/api/animation/projects/consistency-check", "consistency"),
            ("/api/animation/projects/scene-pacing", "scene_pacing"),
            ("/api/animation/projects/climax-plan", "climax"),
        ]:
            resp = client.post(path, json=SAMPLE_PAYLOAD)
            assert_status(resp, 200, path)
            summary[key] = "ok"

        # single render dry-run
        resp = client.post("/api/animation/projects/render", json=SAMPLE_PAYLOAD)
        assert_status(resp, 200, "render")
        task_id = resp.json()["task_id"]
        task = poll_task(client, task_id, timeout=args.timeout)
        if task.get("status") == "failed":
            raise AssertionError(f"render task failed: {json.dumps(task, ensure_ascii=False)[:800]}")
        summary["render_task_status"] = task.get("status")
        summary["render_task_stage"] = task.get("stage")

        # batch render dry-run
        batch_payload = dict(SAMPLE_PAYLOAD)
        batch_payload["episode_goals"] = [
            "伪装关系第一次公开亮相，却因为旧情人出现而失控",
            "直播事故被剪成热搜，男女主被迫继续绑定关系",
        ]
        batch_payload["title_prefix"] = "《失控合约》"
        resp = client.post("/api/animation/projects/render-batch", json=batch_payload)
        assert_status(resp, 200, "render-batch")
        batch_data = resp.json()
        summary["batch_task_id"] = batch_data["batch_task_id"]
        summary["batch_child_count"] = len(batch_data.get("task_ids", []))
        for child_id in batch_data.get("task_ids", []):
            task = poll_task(client, child_id, timeout=args.timeout)
            if task.get("status") == "failed":
                raise AssertionError(f"batch child failed: {child_id}")

        # tasks list
        resp = client.get("/api/animation/tasks")
        assert_status(resp, 200, "tasks")
        tasks = resp.json().get("tasks", [])
        summary["tasks_list_count"] = len(tasks)

    print("animation_api_smoke_v19: ok")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
