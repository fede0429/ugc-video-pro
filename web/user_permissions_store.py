
"""
Simple JSON-backed user permission store.
Keeps per-user UI access and landing preferences without requiring DB migrations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/app/data"))
STORE_DIR = DATA_ROOT / "admin"
STORE_FILE = STORE_DIR / "user_permissions.json"

DEFAULT_PERMISSIONS: dict[str, Any] = {
    "access_ugc": True,
    "access_animation": False,
    "access_testing": False,
    "can_manage_publish": False,
    "default_project": "ugc",
    "notes": "",
}

def _ensure_store() -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        STORE_FILE.write_text("{}", encoding="utf-8")

def _load() -> dict[str, Any]:
    _ensure_store()
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def _save(data: dict[str, Any]) -> None:
    _ensure_store()
    STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize_permissions(raw: dict[str, Any] | None = None, *, role: str = "user") -> dict[str, Any]:
    data = dict(DEFAULT_PERMISSIONS)
    if raw:
        data.update({
            "access_ugc": bool(raw.get("access_ugc", data["access_ugc"])),
            "access_animation": bool(raw.get("access_animation", data["access_animation"])),
            "access_testing": bool(raw.get("access_testing", data["access_testing"])),
            "can_manage_publish": bool(raw.get("can_manage_publish", data["can_manage_publish"])),
            "default_project": raw.get("default_project") or data["default_project"],
            "notes": str(raw.get("notes", data["notes"]) or ""),
        })
    if role == "admin":
        data.update({
            "access_ugc": True,
            "access_animation": True,
            "access_testing": True,
            "can_manage_publish": True,
        })
        if data.get("default_project") not in {"admin", "ugc", "animation"}:
            data["default_project"] = "admin"
    else:
        if data.get("default_project") not in {"ugc", "animation"}:
            data["default_project"] = "ugc"
        if data["default_project"] == "animation" and not data["access_animation"]:
            data["default_project"] = "ugc"
        if data["default_project"] == "ugc" and not data["access_ugc"] and data["access_animation"]:
            data["default_project"] = "animation"
    return data

def get_permissions(user_id: str, *, role: str = "user") -> dict[str, Any]:
    data = _load()
    current = normalize_permissions(data.get(user_id), role=role)
    if role == "admin" and data.get(user_id) != current:
        data[user_id] = current
        _save(data)
    return current

def set_permissions(user_id: str, permissions: dict[str, Any], *, role: str = "user") -> dict[str, Any]:
    data = _load()
    normalized = normalize_permissions(permissions, role=role)
    data[user_id] = normalized
    _save(data)
    return normalized

def list_permissions() -> dict[str, Any]:
    data = _load()
    return data

def resolve_landing(user_id: str, *, role: str = "user") -> str:
    perms = get_permissions(user_id, role=role)
    default_project = perms.get("default_project", "ugc")
    if role == "admin":
        if default_project == "animation":
            return "/animation-studio.html"
        return "/admin.html"
    if default_project == "animation" and perms.get("access_animation"):
        return "/animation-studio.html"
    return "/index.html"
