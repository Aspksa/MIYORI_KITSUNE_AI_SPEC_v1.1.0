from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import (
    connect,
    get_ai_preferences,
    get_project,
    record_audit_event,
    utc_now,
)
from .nexus_actions import build_nexus_action_center
from .nexus_knowledge import build_nexus_knowledge_center


NEXUS_PROACTIVE_SCHEMA_VERSION = "1.0.0"
PROACTIVE_DECISIONS = {"dismissed", "snoozed"}
PROACTIVE_SEVERITIES = {"high", "normal", "low"}
PROACTIVE_DESTINATIONS = {"actions", "knowledge", "system"}
PROACTIVE_CHANNEL_OWNERS = {"presence", "attention_shelf"}


def _fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _signal_id(signal_key: str, fingerprint: str) -> str:
    raw = f"{signal_key}|{fingerprint}".encode("utf-8")
    return "proactive:" + hashlib.sha256(raw).hexdigest()[:18]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _signal(
    *,
    signal_key: str,
    fingerprint_payload: dict[str, Any],
    kind: str,
    severity: str,
    priority: int,
    title: str,
    detail: str,
    destination: str,
    channel_owner: str,
    source: dict[str, Any],
    dismiss_allowed: bool = True,
    snooze_allowed: bool = True,
) -> dict:
    if severity not in PROACTIVE_SEVERITIES:
        raise ValueError("Недопустимая severity proactive signal.")
    if destination not in PROACTIVE_DESTINATIONS:
        raise ValueError("Недопустимое направление proactive signal.")
    if channel_owner not in PROACTIVE_CHANNEL_OWNERS:
        raise ValueError("Недопустимый owner proactive signal.")
    fingerprint = _fingerprint(fingerprint_payload)
    return {
        "id": _signal_id(signal_key, fingerprint),
        "signal_key": signal_key,
        "fingerprint": fingerprint,
        "kind": kind,
        "severity": severity,
        "priority": int(priority),
        "title": title[:180],
        "detail": detail[:360],
        "destination": destination,
        "channel_owner": channel_owner,
        "source": source,
        "controls": {
            "open": True,
            "dismiss": bool(dismiss_allowed),
            "snooze": bool(snooze_allowed),
            "snooze_options_minutes": [60, 1440],
        },
        "safety": {
            "executes_action": False,
            "changes_domain_state": False,
            "requires_existing_permission_flow": True,
        },
    }


def _raw_candidates(project_id: int) -> list[dict]:
    if not get_project(project_id):
        raise ValueError("Проект не найден.")

    action_center = build_nexus_action_center(project_id, limit=80)
    actions = list(action_center.get("actions") or [])
    candidates: list[dict] = []

    for item in actions:
        state = str(item.get("state") or "")
        action_id = str(item.get("id") or "")
        title = str(item.get("title") or "Действие")
        summary = str(item.get("summary") or "").strip()
        operation_id = item.get("operation_id")
        permission_id = item.get("permission_id")
        workflow_id = item.get("workflow_id")
        error = item.get("error")

        if state in {"waiting_permission", "recovery", "error"}:
            if state == "waiting_permission":
                severity = "normal"
                priority = 10
                heading = "Нужно ваше решение"
                fallback = "Подготовлено действие, которое не продолжится без разрешения."
            elif state == "recovery":
                severity = "high"
                priority = 4
                heading = "Нужно восстановить действие"
                fallback = "Workflow остановлен в безопасном recovery-состоянии."
            else:
                severity = "high"
                priority = 5
                heading = "Действие завершилось ошибкой"
                fallback = "Ошибка сохранена в Actions; автоматический повтор не выполняется."

            candidates.append(
                _signal(
                    signal_key=f"action:{action_id}:{state}",
                    fingerprint_payload={
                        "state": state,
                        "operation_id": operation_id,
                        "permission_id": permission_id,
                        "workflow_id": workflow_id,
                        "error": error,
                    },
                    kind="operational",
                    severity=severity,
                    priority=priority,
                    title=f"{heading}: {title}",
                    detail=summary or fallback,
                    destination="actions",
                    channel_owner="presence",
                    source={
                        "type": "action",
                        "id": action_id,
                        "state": state,
                        "operation_id": operation_id,
                        "permission_id": permission_id,
                        "workflow_id": workflow_id,
                    },
                )
            )
            continue

        # "Stale" is evidence-based elapsed time, not an invented deadline.
        if state in {"planned", "running", "verifying"}:
            updated = _parse_time(item.get("updated_at") or item.get("created_at"))
            if updated is not None:
                age_hours = max(0, int((_now_dt() - updated).total_seconds() // 3600))
                if age_hours >= 6:
                    candidates.append(
                        _signal(
                            signal_key=f"action:{action_id}:stale",
                            fingerprint_payload={
                                "state": state,
                                "updated_at": updated.isoformat(),
                                "workflow_id": workflow_id,
                                "operation_id": operation_id,
                            },
                            kind="unfinished_work",
                            severity="low",
                            priority=42,
                            title="Есть незавершённая работа без новых событий",
                            detail=(
                                f"{title}: состояние «{state}» не менялось "
                                f"не менее {age_hours} ч."
                            ),
                            destination="actions",
                            channel_owner="attention_shelf",
                            source={
                                "type": "action",
                                "id": action_id,
                                "state": state,
                                "updated_at": updated.isoformat(),
                                "age_hours": age_hours,
                                "workflow_id": workflow_id,
                            },
                        )
                    )

    knowledge = build_nexus_knowledge_center(project_id, limit=1)
    attention = dict((knowledge.get("counts") or {}).get("attention") or {})
    attention_total = int(attention.get("total") or 0)
    if attention_total > 0:
        parts: list[str] = []
        labels = (
            ("memory_disputed", "спорная память"),
            ("memory_conflicts", "конфликты памяти"),
            ("documents_limited", "ограниченное извлечение документов"),
            ("claim_disputed", "спорные утверждения"),
            ("claim_open_contradictions", "противоречия evidence"),
        )
        for key, label in labels:
            value = int(attention.get(key) or 0)
            if value:
                parts.append(f"{label}: {value}")

        candidates.append(
            _signal(
                signal_key="knowledge:integrity",
                fingerprint_payload={
                    key: int(attention.get(key) or 0)
                    for key, _ in labels
                },
                kind="knowledge_integrity",
                severity="normal",
                priority=30,
                title="В Knowledge есть данные для проверки",
                detail=" · ".join(parts) or f"Элементов для проверки: {attention_total}",
                destination="knowledge",
                channel_owner="attention_shelf",
                source={
                    "type": "knowledge",
                    "attention": {
                        key: int(attention.get(key) or 0)
                        for key, _ in labels
                    },
                },
            )
        )

    discrepancy_parts = {
        "memory_disputed": int(attention.get("memory_disputed") or 0),
        "memory_conflicts": int(attention.get("memory_conflicts") or 0),
        "claim_disputed": int(attention.get("claim_disputed") or 0),
        "claim_open_contradictions": int(attention.get("claim_open_contradictions") or 0),
    }
    discrepancy_total = sum(discrepancy_parts.values())
    if discrepancy_total > 0:
        candidates.append(
            _signal(
                signal_key="knowledge:discrepancy",
                fingerprint_payload=discrepancy_parts,
                kind="knowledge_discrepancy",
                severity="normal",
                priority=22,
                title="Миёри заметила расхождение в знаниях",
                detail=(
                    "Есть подтверждённые системой спорные или противоречащие "
                    f"друг другу записи: {discrepancy_total}."
                ),
                destination="knowledge",
                channel_owner="attention_shelf",
                source={"type": "knowledge", "attention": discrepancy_parts},
            )
        )

    documents_limited = int(attention.get("documents_limited") or 0)
    if documents_limited > 0:
        candidates.append(
            _signal(
                signal_key="knowledge:document_coverage",
                fingerprint_payload={"documents_limited": documents_limited},
                kind="document_coverage_gap",
                severity="normal",
                priority=28,
                title="Часть документов прочитана не полностью",
                detail=(
                    "Ограниченное извлечение текста отмечено у документов: "
                    f"{documents_limited}. Это не считается полным чтением оригинала."
                ),
                destination="knowledge",
                channel_owner="attention_shelf",
                source={
                    "type": "knowledge",
                    "documents_limited": documents_limited,
                },
            )
        )

    evidence_gaps = int(attention.get("claims_need_evidence") or 0)
    if evidence_gaps > 0:
        candidates.append(
            _signal(
                signal_key="knowledge:evidence_gaps",
                fingerprint_payload={"claims_need_evidence": evidence_gaps},
                kind="knowledge_evidence_gap",
                severity="low",
                priority=45,
                title="Некоторым утверждениям не хватает evidence",
                detail=f"Кандидатных утверждений без достаточной независимой поддержки: {evidence_gaps}.",
                destination="knowledge",
                channel_owner="attention_shelf",
                source={
                    "type": "knowledge",
                    "claims_need_evidence": evidence_gaps,
                },
            )
        )

    candidates.sort(
        key=lambda item: (
            int(item["priority"]),
            str(item["signal_key"]),
        )
    )
    return candidates


def _decision_rows(project_id: int) -> dict[tuple[str, str], dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT project_id, signal_key, fingerprint, decision,
                   snoozed_until, created_at, updated_at
            FROM proactive_signal_state
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()
    return {
        (str(row["signal_key"]), str(row["fingerprint"])): dict(row)
        for row in rows
    }


def _preference_budget() -> dict:
    preferences = get_ai_preferences()
    initiative = str(preferences.get("initiative_level") or "medium")
    if initiative not in {"low", "medium", "high"}:
        initiative = "medium"
    suggest = bool(preferences.get("suggest_next_steps", 1))

    max_chat_shelf = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }[initiative]
    if not suggest:
        max_chat_shelf = 0

    return {
        "initiative_level": initiative,
        "suggest_next_steps": suggest,
        "max_contract_signals": 5,
        "max_chat_shelf": max_chat_shelf,
    }


def build_nexus_proactive(project_id: int) -> dict:
    candidates = _raw_candidates(project_id)
    decisions = _decision_rows(project_id)
    budget = _preference_budget()
    now = _now_dt()

    active: list[dict] = []
    suppressed: list[dict] = []
    next_wakeup: datetime | None = None

    for signal in candidates:
        key = (str(signal["signal_key"]), str(signal["fingerprint"]))
        decision = decisions.get(key)
        if decision:
            kind = str(decision.get("decision") or "")
            if kind == "dismissed":
                suppressed.append(
                    {
                        "id": signal["id"],
                        "reason": "dismissed",
                        "signal_key": signal["signal_key"],
                    }
                )
                continue
            if kind == "snoozed":
                until = _parse_time(decision.get("snoozed_until"))
                if until and until > now:
                    suppressed.append(
                        {
                            "id": signal["id"],
                            "reason": "snoozed",
                            "signal_key": signal["signal_key"],
                            "until": until.isoformat(),
                        }
                    )
                    if next_wakeup is None or until < next_wakeup:
                        next_wakeup = until
                    continue

        active.append(signal)

    contract_signals = active[: int(budget["max_contract_signals"])]
    shelf_candidates = [
        item
        for item in active
        if item.get("channel_owner") == "attention_shelf"
    ]

    if budget["initiative_level"] == "medium":
        shelf_candidates = [
            item for item in shelf_candidates if item.get("severity") != "low"
        ]
    elif budget["initiative_level"] == "low":
        shelf_candidates = []

    shelf_ids = [
        str(item["id"])
        for item in shelf_candidates[: int(budget["max_chat_shelf"])]
    ]
    presence_owned_ids = [
        str(item["id"])
        for item in contract_signals
        if item.get("channel_owner") == "presence"
    ]

    return {
        "schema_version": NEXUS_PROACTIVE_SCHEMA_VERSION,
        "project": get_project(project_id),
        "signals": contract_signals,
        "display": {
            "chat_shelf_ids": shelf_ids,
            "presence_owned_ids": presence_owned_ids,
        },
        "budget": {
            **budget,
            "active_candidates": len(active),
            "suppressed_candidates": len(suppressed),
            "selected_chat_shelf": len(shelf_ids),
        },
        "suppressed": suppressed[:20],
        "next_wakeup_at": next_wakeup.isoformat() if next_wakeup else None,
        "policy": {
            "auto_execute_allowed": False,
            "write_action_allowed": False,
            "chat_message_injection_allowed": False,
            "interrupt_user_allowed": False,
            "os_notification_allowed": False,
            "operational_blockers_owned_by_presence": True,
            "decisions_change_signal_visibility_only": True,
        },
        "generated_at": utc_now(),
    }


def apply_proactive_decision(
    project_id: int,
    *,
    signal_key: str,
    fingerprint: str,
    decision: str,
    snooze_minutes: int | None = None,
) -> dict:
    if decision not in PROACTIVE_DECISIONS:
        raise ValueError("Недопустимое решение proactive signal.")

    current = next(
        (
            item
            for item in _raw_candidates(project_id)
            if item.get("signal_key") == signal_key
            and item.get("fingerprint") == fingerprint
        ),
        None,
    )
    if current is None:
        raise ValueError("Proactive signal устарел или больше не существует.")

    controls = current.get("controls") or {}
    if decision == "dismissed" and not controls.get("dismiss"):
        raise ValueError("Этот proactive signal нельзя скрыть.")
    if decision == "snoozed" and not controls.get("snooze"):
        raise ValueError("Этот proactive signal нельзя отложить.")

    now = _now_dt()
    snoozed_until: str | None = None
    if decision == "snoozed":
        minutes = int(snooze_minutes or 60)
        if minutes not in {60, 1440}:
            raise ValueError("Поддерживается snooze на 60 минут или 1 день.")
        snoozed_until = (now + timedelta(minutes=minutes)).isoformat()

    now_text = now.isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO proactive_signal_state(
                project_id, signal_key, fingerprint, decision,
                snoozed_until, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, signal_key, fingerprint)
            DO UPDATE SET
                decision = excluded.decision,
                snoozed_until = excluded.snoozed_until,
                updated_at = excluded.updated_at
            """,
            (
                project_id,
                signal_key,
                fingerprint,
                decision,
                snoozed_until,
                now_text,
                now_text,
            ),
        )

    record_audit_event(
        project_id,
        "user",
        f"proactive.{decision}",
        (
            "Proactive signal скрыт пользователем."
            if decision == "dismissed"
            else "Proactive signal отложен пользователем."
        ),
        entity_type="proactive_signal",
        entity_id=current["id"],
        details={
            "signal_key": signal_key,
            "fingerprint": fingerprint,
            "decision": decision,
            "snoozed_until": snoozed_until,
            "destination": current.get("destination"),
        },
    )

    return {
        "ok": True,
        "decision": decision,
        "signal_id": current["id"],
        "snoozed_until": snoozed_until,
        "proactive": build_nexus_proactive(project_id),
    }
