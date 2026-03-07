import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
html_files = {
    "index": root / "static" / "index.html",
    "animation": root / "static" / "animation-studio.html",
    "admin": root / "static" / "admin.html",
}
js_files = {
    "dashboard": root / "static" / "js" / "dashboard.js",
    "animation": root / "static" / "js" / "animation-dashboard.js",
    "admin": root / "static" / "js" / "admin.js",
}

def extract_ids(text: str):
    return set(re.findall(r'id="([^"]+)"', text))

def extract_getids(text: str):
    ids = set(re.findall(r"getElementById\('([^']+)'\)", text))
    ids.update(re.findall(r'getElementById\("([^"]+)"\)', text))
    return ids

def main():
    html_ids = set()
    for p in html_files.values():
        html_ids |= extract_ids(p.read_text(encoding="utf-8"))
    js_ids = set()
    for p in js_files.values():
        js_ids |= extract_getids(p.read_text(encoding="utf-8"))
    missing = sorted(i for i in js_ids if i not in html_ids)
    print({"missing_ids": missing, "html_count": len(html_ids), "js_count": len(js_ids)})

if __name__ == "__main__":
    main()
