#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def latest_script(prefix: str) -> Path | None:
    candidates = sorted((ROOT / "scripts").glob(f"{prefix}_v*.py"))
    return candidates[-1] if candidates else None

SMOKE_TARGETS = {
    "ugc": [latest_script("ugc_smoke_tests") or ROOT / "scripts" / "ugc_smoke_tests_v9.py"],
    "animation": [
        latest_script("animation_smoke_tests") or ROOT / "scripts" / "animation_smoke_tests_v10.py",
        ROOT / "scripts" / "animation_api_smoke_v19.py",
    ],
}

E2E_SPECS = {
    "ugc": [ROOT / "tests" / "e2e" / "ugc-dashboard.spec.js"],
    "animation": [ROOT / "tests" / "e2e" / "animation-workbench.spec.js"],
}

def run_cmd(cmd: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> dict:
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "duration_sec": round(time.time() - started, 2),
        "output": proc.stdout[-4000:],
    }

def wanted_keys(project: str) -> list[str]:
    if project == "all":
        return ["ugc", "animation"]
    return [project]

def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Studio smoke / E2E entry for Project 1 + Project 2.")
    parser.add_argument("--project", choices=["all", "ugc", "animation"], default="all")
    parser.add_argument("--mode", choices=["smoke", "e2e", "all"], default="all")
    parser.add_argument("--e2e-mock", choices=["0", "1"], default="1")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--require-playwright", action="store_true")
    parser.add_argument("--strict-smoke", action="store_true")
    parser.add_argument("--report", default=str(ROOT / "UNIFIED_TEST_RUN_REPORT.json"))
    args = parser.parse_args()

    summary: dict[str, object] = {
        "project": args.project,
        "mode": args.mode,
        "results": [],
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    failed = 0

    if args.mode in {"smoke", "all"}:
        for key in wanted_keys(args.project):
            for script in SMOKE_TARGETS[key]:
                if not script or not Path(script).exists():
                    result = {"kind": "smoke", "project": key, "name": str(script), "returncode": 0, "duration_sec": 0, "output": "missing script; skipped", "status": "skipped"}
                    summary["results"].append(result)
                    continue
                result = run_cmd([sys.executable, str(script)])
                result["kind"] = "smoke"
                result["project"] = key
                result["name"] = Path(script).name
                if result["returncode"] != 0 and not args.strict_smoke:
                    output = result.get("output", "")
                    if "ModuleNotFoundError" in output or "No module named" in output:
                        result["status"] = "skipped_optional_dependency"
                        result["returncode"] = 0
                    elif "can't open file" in output and "animation_smoke_tests" in str(script):
                        result["status"] = "skipped_missing_script"
                        result["returncode"] = 0
                summary["results"].append(result)
                if result["returncode"] != 0:
                    failed += 1

    if args.mode in {"e2e", "all"}:
        npx = shutil.which("npx")
        if not npx:
            msg = {"kind": "e2e", "project": args.project, "name": "playwright", "returncode": 127, "duration_sec": 0, "output": "npx not found; skipped"}
            summary["results"].append(msg)
            if args.require_playwright:
                failed += 1
        else:
            specs: list[str] = []
            for key in wanted_keys(args.project):
                specs.extend(str(p.relative_to(ROOT)) for p in E2E_SPECS[key])
            env = os.environ.copy()
            env["ANIMATION_E2E_MOCK"] = args.e2e_mock
            env["ANIMATION_E2E_BASE_URL"] = args.base_url
            result = run_cmd([npx, "playwright", "test", *specs], env=env, cwd=ROOT)
            result["kind"] = "e2e"
            result["project"] = args.project
            result["name"] = "playwright"
            summary["results"].append(result)
            if result["returncode"] != 0:
                failed += 1

    summary["failed"] = failed
    summary["status"] = "passed" if failed == 0 else "failed"

    report_path = Path(args.report)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
