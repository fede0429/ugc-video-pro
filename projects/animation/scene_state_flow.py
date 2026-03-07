from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class SceneTransition:
    from_scene_id: str
    to_scene_id: str
    transition_type: str
    emotional_shift: str
    time_jump: str
    location_shift: str
    carry_over_props: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class SceneStateFlowEngine:
    def build(self, episode) -> dict:
        transitions: list[dict] = []
        scenes = episode.scenes or []
        for idx in range(len(scenes) - 1):
            current = scenes[idx]
            nxt = scenes[idx + 1]
            current_loc = current.location or current.title
            next_loc = nxt.location or nxt.title
            location_shift = "same_location" if current_loc == next_loc else "location_change"
            emotional = self._emotion_shift(current, nxt)
            carry = self._carry_over_props(current, nxt)
            transition = SceneTransition(
                from_scene_id=current.scene_id,
                to_scene_id=nxt.scene_id,
                transition_type="hard_cut" if location_shift == "location_change" else "match_cut",
                emotional_shift=emotional,
                time_jump="continuous" if idx == 0 else "short_jump",
                location_shift=location_shift,
                carry_over_props=carry,
                notes=[
                    f"from:{current_loc}",
                    f"to:{next_loc}",
                    f"beats:{len(current.beats)}->{len(nxt.beats)}",
                ],
            )
            transitions.append(transition.to_dict())
        return {
            "scene_count": len(scenes),
            "transitions": transitions,
            "scene_order": [s.scene_id for s in scenes],
        }

    def _emotion_shift(self, current, nxt) -> str:
        c = " ".join(current.beats).lower()
        n = " ".join(nxt.beats).lower()
        if any(k in n for k in ["冲突", "崩", "怒", "panic", "fight"]):
            return "rise_tension"
        if any(k in n for k in ["和解", "soft", "拥抱", "reveal"]):
            return "release_then_reveal"
        if c == n:
            return "steady"
        return "progressive_shift"

    def _carry_over_props(self, current, nxt) -> list[str]:
        shared = []
        joined_current = " ".join(current.beats)
        joined_next = " ".join(nxt.beats)
        for token in ["手机", "合同", "戒指", "文件", "phone", "ring", "contract", "letter"]:
            if token in joined_current and token in joined_next:
                shared.append(token)
        if not shared:
            shared.append("character_expression_memory")
        return shared
