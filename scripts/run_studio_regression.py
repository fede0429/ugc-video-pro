#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "STUDIO_REGRESSION_REPORT_V24.json"

def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 90) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "cwd": str(cwd or ROOT),
            "returncode": proc.returncode,
            "duration_sec": round(time.time() - started, 2),
            "output": proc.stdout[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "cwd": str(cwd or ROOT),
            "returncode": 124,
            "duration_sec": round(time.time() - started, 2),
            "output": ((exc.stdout or "") + "\nTIMEOUT")[-12000:],
        }

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the studio regression bundle.")
    parser.add_argument("--with-e2e", action="store_true", help="Run Playwright E2E after smoke.")
    parser.add_argument("--e2e-mock", default="1", choices=["0", "1"], help="Use mock mode for Playwright.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL for real-backend E2E.")
    parser.add_argument("--strict", action="store_true", help="Fail on any non-zero step.")
    args = parser.parse_args()

    env = os.environ.copy()
    env["ANIMATION_E2E_MOCK"] = args.e2e_mock
    env["ANIMATION_E2E_BASE_URL"] = args.base_url

    results = [
        run_cmd([sys.executable, "-m", "compileall", "-q", "core", "projects", "services", "web", "scripts"]),
        run_cmd([sys.executable, "scripts/studio_e2e_audit.py"]),
        run_cmd([sys.executable, "scripts/studio_test_hub.py", "--mode", "smoke", "--project", "all"], timeout=180),
        run_cmd(["node", "--check", "tests/e2e/studio-e2e-matrix.spec.js"]),
        run_cmd(["node", "--check", "tests/e2e/ugc-dashboard.spec.js"]),
        run_cmd(["node", "--check", "tests/e2e/animation-workbench.spec.js"]),
    ]

    if args.with_e2e:
        results.append(
            run_cmd(
                ["npx", "playwright", "test", "tests/e2e/studio-e2e-matrix.spec.js"],
                env=env,
                timeout=600,
            )
        )

    overall_rc = 0
    for item in results:
        if item["returncode"] != 0:
            overall_rc = item["returncode"]
            if args.strict:
                break

    payload = {
        "version": "v24",
        "with_e2e": args.with_e2e,
        "e2e_mock": args.e2e_mock,
        "base_url": args.base_url,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "overall_returncode": overall_rc,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(json.dumps({"overall_returncode": overall_rc, "steps": len(results)}, ensure_ascii=False))
    return overall_rc

if __name__ == "__main__":
    raise SystemExit(main())
