
from __future__ import annotations

import time
from typing import Any


class ReviewStateMachine:
    ALLOWED: dict[str, set[str]] = {
        "draft": {"in_review", "rejected", "approved"},
        "in_review": {"approved", "rejected", "needs_changes"},
        "needs_changes": {"draft", "in_review"},
        "approved": {"publish_ready", "archived"},
        "publish_ready": {"published", "failed_publish", "archived"},
        "failed_publish": {"publish_ready", "archived"},
        "published": {"archived"},
        "rejected": {"archived", "draft"},
        "archived": set(),
    }

    def can_transition(self, old: str, new: str) -> bool:
        if old == new:
            return True
        return new in self.ALLOWED.get(old, set())

    def transition(self, current: dict[str, Any] | None, *, new_status: str, actor: str = "system", note: str = "") -> dict[str, Any]:
        current = dict(current or {})
        old_status = current.get("status", "draft")
        if not self.can_transition(old_status, new_status):
            raise ValueError(f"Illegal review transition: {old_status} -> {new_status}")
        history = list(current.get("history", []))
        history.append({
            "from": old_status,
            "to": new_status,
            "actor": actor,
            "note": note,
            "ts": time.time(),
        })
        return {
            "status": new_status,
            "actor": actor,
            "note": note,
            "updated_at": time.time(),
            "history": history,
        }
