
from __future__ import annotations

from dataclasses import dataclass, asdict

from core.timeline_types import QAReport, TimelineScript


@dataclass
class VideoScoreReport:
    total_score: int
    hook_strength_score: int
    clarity_score: int
    rhythm_score: int
    authenticity_score: int
    product_visibility_score: int
    issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class VideoScoringService:
    def score(self, timeline: TimelineScript, qa_report: QAReport | None = None) -> VideoScoreReport:
        issues: list[str] = []
        recommendations: list[str] = []
        segs = timeline.segments or []
        first = segs[0] if segs else None

        hook = 60
        if first and ((first.overlay_text or "").strip() or (first.spoken_line or "").strip()):
            hook += 18
        if first and first.track_type == "a_roll":
            hook += 6
        if first and len((first.overlay_text or "")[:20]) <= 12:
            hook += 6
        if first and any(k in ((first.spoken_line or "") + " " + (first.overlay_text or "")).lower() for k in ["为什么", "后悔", "must", "need", "problem", "别再", "真的"]):
            hook += 10

        clarity = 68
        if any((s.spoken_line or "").strip() for s in segs):
            clarity += 8
        if any((s.overlay_text or "").strip() for s in segs):
            clarity += 8
        if segs and all(float(s.duration_seconds) >= 3 for s in segs):
            clarity += 6

        rhythm = 65
        broll_count = sum(1 for s in segs if s.track_type == "b_roll")
        aroll_count = sum(1 for s in segs if s.track_type == "a_roll")
        if broll_count and aroll_count:
            rhythm += 12
        if len(segs) >= 4:
            rhythm += 10
        if any((s.camera_movement or "") not in ("", "static") for s in segs):
            rhythm += 7

        authenticity = 64
        if any("handheld" in (s.camera_movement or "") for s in segs):
            authenticity += 10
        if any("demo" in (s.shot_type or "") or "hands" in (s.shot_type or "") for s in segs):
            authenticity += 10
        if any("natural" in (s.visual_prompt or "").lower() or "真实" in (s.scene_description or "") for s in segs):
            authenticity += 8

        product_visibility = 66
        if any((s.product_focus or "").strip() for s in segs):
            product_visibility += 10
        if any((s.b_roll_prompt or "").strip() for s in segs):
            product_visibility += 8
        if any("detail" in (s.shot_type or "") or "macro" in (s.shot_type or "") or "packshot" in (s.shot_type or "") for s in segs):
            product_visibility += 8

        if qa_report and not qa_report.passed:
            issues.extend([f"{i.severity}:{i.message}" for i in qa_report.issues])
            hook -= 4; clarity -= 4; rhythm -= 4; authenticity -= 4; product_visibility -= 4

        if hook < 75:
            recommendations.append("开头 3 秒建议再强化，用更直接的痛点或结果型 hook。")
        if clarity < 75:
            recommendations.append("字幕和口播信息密度还可提升，让卖点更直白。")
        if rhythm < 76:
            recommendations.append("建议增加 B-roll 切换频率，减少段落平均感。")
        if authenticity < 72:
            recommendations.append("真实感偏弱，建议增加手持镜头、环境感和生活化动作。")
        if product_visibility < 74:
            recommendations.append("产品锚点不足，建议增加细节特写或 hero product shot。")

        total = round((hook + clarity + rhythm + authenticity + product_visibility) / 5)
        if total < 75:
            recommendations.append("建议先多做 hook 变体测试，再批量生产。")

        return VideoScoreReport(
            total_score=max(0, min(100, total)),
            hook_strength_score=max(0, min(100, hook)),
            clarity_score=max(0, min(100, clarity)),
            rhythm_score=max(0, min(100, rhythm)),
            authenticity_score=max(0, min(100, authenticity)),
            product_visibility_score=max(0, min(100, product_visibility)),
            issues=issues,
            recommendations=recommendations,
        )
