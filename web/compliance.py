"""
web/compliance.py
=================
Internal rights-manifest validation and compliance-token helpers.
This module validates user-supplied rights_manifest.json before any真人素材任务进入模型平台。
"""
from __future__ import annotations

import hashlib
import json
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_LANGUAGES = {"zh", "en", "it"}
SUPPORTED_PLATFORMS = {"douyin", "xiaohongshu", "tiktok", "youtube"}


@dataclass
class ComplianceValidationResult:
    normalized_manifest: dict[str, Any]
    summary: dict[str, Any]
    compliance_token: str


def _parse_iso_date(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} 格式无效，必须为 YYYY-MM-DD 或 ISO 时间") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_sha256_for_path(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest_bytes(content: bytes) -> dict[str, Any]:
    try:
        data = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise ValueError("rights_manifest.json 不是有效的 UTF-8 JSON 文件") from exc
    if not isinstance(data, dict):
        raise ValueError("rights_manifest.json 顶层必须是 JSON 对象")
    return data


def validate_rights_manifest(
    *,
    manifest: dict[str, Any],
    selected_language: str,
    selected_platform: str,
    has_presenter_image: bool,
    has_presenter_video: bool,
    presenter_image_sha256: str | None,
    presenter_video_sha256: str | None,
    consent_confirmed: bool,
) -> ComplianceValidationResult:
    normalized = deepcopy(manifest)
    now = datetime.now(timezone.utc)

    version = str(normalized.get("version") or "1.0")
    normalized["version"] = version

    if not consent_confirmed:
        raise ValueError("使用真人数字人素材时，必须勾选“我确认已获得合法授权”")

    if not normalized.get("consent_confirmed", False):
        raise ValueError("rights_manifest.json 缺少 consent_confirmed=true")

    subject_type = str(normalized.get("subject_type") or "").strip()
    if subject_type not in {"real_person", "licensed_avatar", "brand_spokesperson"}:
        raise ValueError("subject_type 必须是 real_person / licensed_avatar / brand_spokesperson")

    rights_owner = str(normalized.get("rights_owner") or "").strip()
    if not rights_owner:
        raise ValueError("rights_owner 不能为空")

    authorization_basis = str(normalized.get("authorization_basis") or "").strip()
    if not authorization_basis:
        raise ValueError("authorization_basis 不能为空")

    valid_from = _parse_iso_date(normalized.get("valid_from"), "valid_from")
    valid_until = _parse_iso_date(normalized.get("valid_until"), "valid_until")
    if valid_from and now < valid_from:
        raise ValueError("授权尚未生效，当前时间早于 valid_from")
    if valid_until and now > valid_until:
        raise ValueError("授权已过期，当前时间晚于 valid_until")
    if valid_from and valid_until and valid_until < valid_from:
        raise ValueError("valid_until 不能早于 valid_from")

    usage_scope = normalized.get("usage_scope") or {}
    if not isinstance(usage_scope, dict):
        raise ValueError("usage_scope 必须是对象")

    languages = usage_scope.get("languages") or []
    if not isinstance(languages, list) or not languages:
        raise ValueError("usage_scope.languages 必须是非空数组")
    lang_set = {str(x).strip() for x in languages if str(x).strip()}
    if selected_language not in lang_set:
        raise ValueError(f"授权范围不包含所选语言：{selected_language}")
    if not lang_set.issubset(SUPPORTED_LANGUAGES | {"zh-CN", "en-US", "it-IT"}):
        raise ValueError("usage_scope.languages 包含系统不支持的语言代码")

    platforms = usage_scope.get("platforms") or usage_scope.get("channels") or []
    if not isinstance(platforms, list) or not platforms:
        raise ValueError("usage_scope.platforms 必须是非空数组")
    platform_set = {str(x).strip() for x in platforms if str(x).strip()}
    if selected_platform not in platform_set:
        raise ValueError(f"授权范围不包含所选平台：{selected_platform}")

    allow_lipsync = bool(usage_scope.get("allow_lipsync", False))
    allow_face_reenactment = bool(usage_scope.get("allow_face_reenactment", False))

    if has_presenter_image and not allow_lipsync:
        raise ValueError("授权范围未允许 allow_lipsync，不能使用真人头像口播")
    if has_presenter_video and not allow_face_reenactment:
        raise ValueError("授权范围未允许 allow_face_reenactment，不能使用主播短视频")

    bound_assets = normalized.get("bound_assets") or {}
    if not isinstance(bound_assets, dict):
        raise ValueError("bound_assets 必须是对象")

    if has_presenter_image:
        if not presenter_image_sha256:
            raise ValueError("系统未拿到 presenter_image_sha256")
        existing = str(bound_assets.get("presenter_image_sha256") or "").strip()
        if existing and existing != presenter_image_sha256:
            raise ValueError("rights_manifest.json 中 presenter_image_sha256 与当前上传图片不匹配")
        bound_assets["presenter_image_sha256"] = presenter_image_sha256

    if has_presenter_video:
        if not presenter_video_sha256:
            raise ValueError("系统未拿到 presenter_video_sha256")
        existing = str(bound_assets.get("presenter_video_sha256") or "").strip()
        if existing and existing != presenter_video_sha256:
            raise ValueError("rights_manifest.json 中 presenter_video_sha256 与当前上传视频不匹配")
        bound_assets["presenter_video_sha256"] = presenter_video_sha256

    normalized["bound_assets"] = bound_assets

    evidence_files = normalized.get("evidence_files") or []
    if evidence_files and not isinstance(evidence_files, list):
        raise ValueError("evidence_files 必须是数组")

    compliance_seed = json.dumps({
        "rights_owner": rights_owner,
        "subject_type": subject_type,
        "valid_until": normalized.get("valid_until"),
        "bound_assets": bound_assets,
    }, ensure_ascii=False, sort_keys=True)
    token = "cmp_" + hashlib.sha256((compliance_seed + secrets.token_hex(8)).encode("utf-8")).hexdigest()[:20]

    summary = {
        "status": "approved",
        "subject_type": subject_type,
        "rights_owner": rights_owner,
        "authorization_basis": authorization_basis,
        "valid_from": normalized.get("valid_from"),
        "valid_until": normalized.get("valid_until"),
        "languages": sorted(lang_set),
        "platforms": sorted(platform_set),
        "allow_lipsync": allow_lipsync,
        "allow_face_reenactment": allow_face_reenactment,
        "bound_assets": bound_assets,
        "evidence_count": len(evidence_files),
    }

    return ComplianceValidationResult(
        normalized_manifest=normalized,
        summary=summary,
        compliance_token=token,
    )
