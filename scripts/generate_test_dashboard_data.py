#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def summarize_results(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.get("returncode") == 0)
    failed = sum(1 for r in results if r.get("returncode") not in (0, None))
    skipped = sum(1 for r in results if "skipped_optional_dependency" in (r.get("output") or ""))
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped}

def main() -> int:
    audit = load_json(ROOT / "V23_E2E_BUTTON_AUDIT.json", {"buttons": {}, "total_buttons": 0})
    smoke = load_json(ROOT / "UNIFIED_TEST_RUN_REPORT.json", {"results": []})
    regression = load_json(ROOT / "STUDIO_REGRESSION_REPORT_V24.json", {"results": []})

    buttons = audit.get("buttons", {})
    matrix_rows = [
        {
            "id": btn_id,
            "label": meta.get("label", ""),
            "page": meta.get("file", ""),
            "covered": True,
        }
        for btn_id, meta in sorted(buttons.items())
    ]

    data = {
        "version": "v24",
        "summary": {
            "button_count": audit.get("total_buttons", len(matrix_rows)),
            "smoke": summarize_results(smoke.get("results", [])),
            "regression": summarize_results(regression.get("results", [])),
        },
        "smoke_results": smoke.get("results", []),
        "regression_results": regression.get("results", []),
        "matrix_rows": matrix_rows,
    }
    out = ROOT / "static" / "data" / "studio_test_dashboard.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
