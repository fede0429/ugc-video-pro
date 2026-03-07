
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from .models import CharacterBible, EpisodePlan


@dataclass
class CharacterState:
    character_name: str
    state_id: str
    emotion: str
    posture: str
    objective: str
    energy_level: str
    expression_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CharacterStateMachine:
    def build_for_characters(self, characters: list[CharacterBible]) -> dict[str, dict]:
        payload: dict[str, dict] = {}
        for c in characters:
            payload[c.name] = {
                "default_state": "baseline",
                "states": [
                    CharacterState(c.name, "baseline", "克制", "站姿稳定", "维持表面平静", "medium", ["neutral gaze", "controlled breathing"]).to_dict(),
                    CharacterState(c.name, "confrontation", "愤怒压制", "身体前倾", "压制对手", "high", ["sharp eyes", "tight jaw"]).to_dict(),
                    CharacterState(c.name, "vulnerable", "脆弱", "轻微后撤", "隐藏真实情绪", "low", ["wet eyes", "micro tremble"]).to_dict(),
                    CharacterState(c.name, "resolve", "坚定", "稳步向前", "做出决断", "high", ["focused stare", "firm mouth"]).to_dict(),
                ],
                "transitions": [
                    {"from": "baseline", "to": "confrontation", "trigger": "受到挑衅或信息冲击"},
                    {"from": "confrontation", "to": "vulnerable", "trigger": "真相暴露或关系刺痛"},
                    {"from": "vulnerable", "to": "resolve", "trigger": "决定反击或自我确认"},
                    {"from": "baseline", "to": "resolve", "trigger": "直接拿到关键证据"},
                ],
            }
        return payload

    def apply_to_episode(self, episode: EpisodePlan, state_map: dict[str, dict]) -> dict[str, list[dict]]:
        applied: dict[str, list[dict]] = {}
        scene_states = ["baseline", "confrontation", "vulnerable", "resolve"]
        for scene_idx, scene in enumerate(episode.scenes):
            target_state = scene_states[min(scene_idx, len(scene_states)-1)]
            for shot in scene.shots:
                matched = []
                for name, payload in state_map.items():
                    states = payload.get("states", [])
                    state = next((s for s in states if s["state_id"] == target_state), None) or next((s for s in states if s["state_id"] == payload.get("default_state")), None)
                    if not state:
                        continue
                    shot.continuity_notes.append(f"character_state:{name}:{state['state_id']}")
                    shot.continuity_notes.append(f"state_objective:{name}:{state['objective']}")
                    if state.get("expression_keywords"):
                        shot.continuity_notes.append(f"expression_anchor:{name}:{', '.join(state['expression_keywords'])}")
                    matched.append({
                        "character_name": name,
                        "state_id": state["state_id"],
                        "objective": state["objective"],
                        "emotion": state["emotion"],
                    })
                applied[shot.shot_id] = matched
        return applied
