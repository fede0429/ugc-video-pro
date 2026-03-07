
from __future__ import annotations
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HTML_FILES = [
    ROOT / "static" / "index.html",
    ROOT / "static" / "animation-studio.html",
]

SPEC_FILES = [
    ROOT / "tests" / "e2e" / "ugc-dashboard.spec.js",
    ROOT / "tests" / "e2e" / "animation-workbench.spec.js",
    ROOT / "tests" / "e2e" / "studio-e2e-matrix.spec.js",
]

def extract_buttons(html_text: str):
    return re.findall(r'<button[^>]*id="([^"]+)"[^>]*>(.*?)</button>', html_text, flags=re.I | re.S)

def extract_id_refs(js_text: str):
    ids = set(re.findall(r"(?:getByTestId|getByRole\([^)]*name:\s*['\"]([^'\"]+)['\"])", js_text))
    ids |= set(re.findall(r"#([A-Za-z0-9_-]+)", js_text))
    ids |= set(re.findall(r"getByRole\('button', \{ name: /([^/]+)/i \}\)", js_text))
    return ids

def main():
    buttons = {}
    for html in HTML_FILES:
        text = html.read_text(encoding="utf-8")
        for btn_id, label in extract_buttons(text):
            label = re.sub(r"\s+", " ", label).strip()
            buttons[btn_id] = {"label": label, "file": html.name}
    refs = set()
    for spec in SPEC_FILES:
        if spec.exists():
            refs |= extract_id_refs(spec.read_text(encoding="utf-8"))
    report = {
        "total_buttons": len(buttons),
        "buttons": buttons,
        "referenced_tokens": sorted(refs),
    }
    out = ROOT / "V23_E2E_BUTTON_AUDIT.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"buttons={len(buttons)} audit={out}")

if __name__ == "__main__":
    main()
