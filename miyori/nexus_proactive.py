from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, get_ai_preferences, get_project, record_audit_event
from .nexus import build_nexus_snapshot
from .nexus_actions import build_nexus_action_center
from .nexus_knowledge import build_nexus_knowledge_center


NEXUS_PROACTIVE_SCHEMA_VERSION = "1.0.0"
PROACTIVE_PRIORITIES = {"high", "normal", "low"}
PROACTIVE_DISPOSITIONS = {"dismissed", "snoozed"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def init_proactive_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS proactive_signal_state (
                project_id INTEGER NOT NULL,
                signal_id TEXT NOT NULL,
                signal_key TEXT NOT NULL,
                disposition TEXT NOT NULL CHECK(disposition IN ('dismissed','snoozed')),
                snoozed_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id, signal_id),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_proactive_signal_state_project
            ON proactive_signal_state(project_id, disposition, updated_at DESC);
            """
        )


def _signal_id(project_id: int, signal_key: str) -> str:
    digest = hashlib.sha256(
        f"{int(project_id)}:{signal_key}".encode("utf-8")
    ).hexdigest()
    return digest[:20]


def _signal(
    project_id: int,
    *,
    signal_key: str,
    category: str,
    priority: str,
    title: str,
    detail: str,
    target: str,
    source: dict,
) -> dict:
    if priority not in PROACTIVE_PRIORITIES:
        raise ValueError("Недопустимый proactive priority.")
    return {
        "id": _signal_id(project_id, signal_key),
        "signal_key": signal_key,
        "category": category,
        "priority": priority,
        "title": title,
        "detail": detail,
        "source": source,
        "action": {
            "type": "navigate",
            "target": target,
            "label": {
                "actions": "Открыть действия",
                "knowledge": "Открыть знания",
                "system": "Открыть систему",
            }.get(target, "Открыть"),
        },
        "controls": {
            "can_snooze": True,
            "can_dismiss": True,
        },
        "policy": {
            "auto_execute_allowed": False,
            "write_tools_allowed": False,
            "chat_interruption_allowed": False,
            "creates_chat_message": False,
            "requires_explicit_user_action": True,
        },
    }


def _knowledge_fingerprint(knowledge: dict) -> str:
    items: list[str] = []
    for item in knowledge.get("memory") or []:
        if item.get("status") == "disputed" or item.get("possible_conflict_ids"):
            items.append(
                f"memory:{item.get('id')}:{item.get('status')}:"
                + ",".join(str(value) for value in item.get("possible_conflict_ids") or [])
            )
    for item in knowledge.get("documents") or []:
        intelligence = item.get("intelligence") or {}
        if intelligence.get("limited"):
            items.append(
                f"document:{item.get('id')}:{intelligence.get('status')}:"
                f"{float(intelligence.get('extraction_coverage') or 0.0):.4f}"
            )
    for item in knowledge.get("claims") or []:
        if item.get("status") in {"disputed", "rejected"} or int(
            item.get("open_contradictions") or 0
        ) > 0:
            items.append(
                f"claim:{item.get('id')}:{item.get('status')}:"
                f"{int(item.get('open_contradictions') or 0)}"
            )
    raw = json.dumps(sorted(items), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _candidates(project_id: int) -> tuple[list[dict], dict, dict]:
    snapshot = build_nexus_snapshot(project_id)
    action_center = build_nexus_action_center(project_id, limit=80)
    preferences = get_ai_preferences() or {}

    candidates: list[dict] = []
    for item in action_center.get("actions") or []:
        state = str(item.get("state") or "")
        if state not in {"waiting_permission", "recovery", "error"}:
            continue
        if state == "recovery":
            priority = "high"
            title = "Нужно безопасно восстановить действие"
            detail = str(item.get("summary") or item.get("title") or "")
        elif state == "error":
            priority = "high"
            title = "Действие завершилось ошибкой"
            detail = str(item.get("title") or item.get("summary") or "")
        else:
            priority = "normal"
            title = "Нужно ваше решение"
            detail = str(item.get("summary") or item.get("title") or "")

        candidates.append(
            _signal(
                project_id,
                signal_key=f"action:{item.get('id')}:{state}",
                category="action",
                priority=priority,
                title=title,
                detail=detail,
                target="actions",
                source={
                    "kind": "nexus_action",
                    "id": item.get("id"),
                    "state": state,
                    "workflow_id": item.get("workflow_id"),
                    "permission_id": item.get("permission_id"),
                },
            )
        )

    suggest_next_steps = bool(preferences.get("suggest_next_steps", 1))
    knowledge_attention = int(snapshot.get("counts", {}).get("knowledge_attention") or 0)
    knowledge: dict = {}
    if suggest_next_steps and knowledge_attention > 0:
        knowledge = build_nexus_knowledge_center(project_id, limit=120)
        attention = knowledge.get("counts", {}).get("attention") or {}
        fingerprint = _knowledge_fingerprint(knowledge)
        open_contradictions = int(attention.get("claim_open_contradictions") or 0)
        candidates.append(
            _signal(
                project_id,
                signal_key=f"knowledge:{fingerprint}",
                category="knowledge",
                priority="normal" if open_contradictions else "low",
                title=(
                    "Есть противоречия в знаниях"
                    if open_contradictions
                    else "Есть знания, которые стоит проверить"
                ),
                detail=(
                    f"Открытых противоречий: {open_contradictions}."
                    if open_contradictions
                    else f"Элементов для проверки: {knowledge_attention}."
                ),
                target="knowledge",
                source={
                    "kind": "knowledge_attention",
                    "fingerprint": fingerprint,
                    "attention": attention,
                },
            )
        )

    priority_rank = {"high": 0, "normal": 1, "low": 2}
    candidates.sort(
        key=lambda item: (
            priority_rank[str(item["priority"])],
            str(item["id"]),
        )
    )
    return candidates, snapshot, preferences


def _states(project_id: int) -> dict[str, dict]:
    init_proactive_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT project_id, signal_id, signal_key, disposition,
                   snoozed_until, created_at, updated_at
            FROM proactive_signal_state
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()
    return {str(row["signal_id"]): dict(row) for row in rows}


def _is_suppressed(state: dict | None, now: datetime) -> tuple[bool, str | None]:
    if not state:
        return False, None
    disposition = str(state.get("disposition") or "")
    if disposition == "dismissed":
        return True, "dismissed"
    if disposition == "snoozed":
        raw = state.get("snoozed_until")
        if not raw:
            return False, None
        try:
            until = datetime.fromisoformat(str(raw))
        except ValueError:
            return False, None
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until > now:
            return True, "snoozed"
    return False, None


def _budget(preferences: dict) -> dict:
    initiative = str(preferences.get("initiative_level") or "medium")
    if initiative == "low":
        return {"max_visible": 1, "max_low": 0}
    if initiative == "high":
        return {"max_visible": 3, "max_low": 1}
    return {"max_visible": 2, "max_low": 1}


def build_nexus_proactive(project_id: int, *, limit: int | None = None) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")

    candidates, snapshot, preferences = _candidates(project_id)
    persisted = _states(project_id)
    now = _now_dt()
    budget = _budget(preferences)
    max_visible = int(budget["max_visible"])
    if limit is not None:
        max_visible = max(1, min(max_visible, int(limit), 5))

    visible: list[dict] = []
    snoozed = 0
    dismissed = 0
    budget_suppressed = 0
    low_used = 0

    for item in candidates:
        suppressed, reason = _is_suppressed(persisted.get(str(item["id"])), now)
        if suppressed:
            if reason == "snoozed":
                snoozed += 1
            elif reason == "dismissed":
                dismissed += 1
            continue

        if len(visible) >= max_visible:
            budget_suppressed += 1
            continue
        if item["priority"] == "low":
            if low_used >= int(budget["max_low"]):
                budget_suppressed += 1
                continue
            low_used += 1
        visible.append(item)

    return {
        "schema_version": NEXUS_PROACTIVE_SCHEMA_VERSION,
        "project": snapshot["project"],
        "enabled": True,
        "initiative_level": str(preferences.get("initiative_level") or "medium"),
        "signals": visible,
        "counts": {
            "candidates": len(candidates),
            "visible": len(visible),
            "snoozed": snoozed,
            "dismissed": dismissed,
            "budget_suppressed": budget_suppressed,
        },
        "budget": {
            **budget,
            "effective_max_visible": max_visible,
            "used": len(visible),
        },
        "policy": {
            "chat_interruption_allowed": False,
            "auto_execute_allowed": False,
            "write_tools_allowed": False,
            "creates_chat_messages": False,
            "persistent_dismiss_snooze": True,
            "derived_from_authoritative_state": True,
        },
        "generated_at": _now(),
    }


def set_proactive_disposition(
    project_id: int,
    signal_id: str,
    *,
    disposition: str,
    snooze_minutes: int | None = None,
) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")
    clean_id = str(signal_id or "").strip().lower()
    if len(clean_id) != 20 or any(ch not in "0123456789abcdef" for ch in clean_id):
        raise ValueError("Некорректный proactive signal id.")
    if disposition not in PROACTIVE_DISPOSITIONS:
        raise ValueError("Некорректное proactive disposition.")

    candidates, _, _ = _candidates(project_id)
    current = next((item for item in candidates if item["id"] == clean_id), None)
    if not current:
        raise ValueError("Proactive signal больше не актуален.")

    now = _now_dt()
    snoozed_until = None
    if disposition == "snoozed":
        minutes = max(15, min(int(snooze_minutes or 60), 10080))
        snoozed_until = (now + timedelta(minutes=minutes)).isoformat()

    init_proactive_db()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM proactive_signal_state
            WHERE project_id = ? AND signal_id = ?
            """,
            (project_id, clean_id),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else now.isoformat()
        conn.execute(
            """
            INSERT INTO proactive_signal_state(
                project_id, signal_id, signal_key, disposition,
                snoozed_until, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, signal_id) DO UPDATE SET
                signal_key = excluded.signal_key,
                disposition = excluded.disposition,
                snoozed_until = excluded.snoozed_until,
                updated_at = excluded.updated_at
            """,
            (
                project_id,
                clean_id,
                current["signal_key"],
                disposition,
                snoozed_until,
                created_at,
                now.isoformat(),
            ),
        )

    record_audit_event(
        project_id,
        "user",
        f"proactive.{disposition}",
        (
            "Proactive-сигнал скрыт пользователем."
            if disposition == "dismissed"
            else "Proactive-сигнал отложен пользователем."
        ),
        entity_type="proactive_signal",
        entity_id=clean_id,
        details={
            "signal_key": current["signal_key"],
            "category": current["category"],
            "priority": current["priority"],
            "snoozed_until": snoozed_until,
        },
    )

    return {
        "ok": True,
        "signal_id": clean_id,
        "disposition": disposition,
        "snoozed_until": snoozed_until,
    }
