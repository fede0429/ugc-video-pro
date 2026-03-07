
from pathlib import Path
import re, sys
root = Path(__file__).resolve().parents[1]
html = (root / "static/animation-studio.html").read_text(encoding="utf-8", errors="ignore")
js = (root / "static/js/animation-dashboard.js").read_text(encoding="utf-8", errors="ignore")
html_ids = set(re.findall(r'id="([^"]+)"', html))
js_ids = set(re.findall(r"getElementById\('([^']+)'\)", js))
missing = sorted(js_ids - html_ids)
print("missing_ids", missing)
sys.exit(1 if missing else 0)
