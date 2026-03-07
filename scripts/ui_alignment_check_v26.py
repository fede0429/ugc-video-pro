
from pathlib import Path
import re, json

root = Path(__file__).resolve().parents[1]
pairs = [
    (root / "static/index.html", root / "static/js/dashboard.js"),
    (root / "static/admin.html", root / "static/js/admin.js"),
    (root / "static/admin-permissions.html", root / "static/js/admin-permissions.js"),
]
report = {}
for html_path, js_path in pairs:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    js = js_path.read_text(encoding="utf-8", errors="ignore")
    ids = set(re.findall(r'id="([^"]+)"', html))
    refs = set(re.findall(r"getElementById\('([^']+)'\)", js)) | set(re.findall(r'getElementById\("([^"]+)"\)', js))
    missing = sorted(refs - ids)
    report[html_path.name] = {"missing_ids": missing, "ref_count": len(refs), "id_count": len(ids)}
print(json.dumps(report, ensure_ascii=False, indent=2))
