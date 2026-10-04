from __future__ import annotations

from datetime import datetime, timezone

from .nexus import build_nexus_snapshot
from .nexus_actions import build_nexus_action_center
from .nexus_events import list_nexus_events


NEXUS_PRESENCE_SCHEMA_VERSION = "1.0.0"
NEXUS_PRESENCE_MODES = {
    "ready",
    "working",
    "verifying",
    "waiting",
    "attention",
    "recovery",
    "degraded",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reason(kind: str, label: str, *, state: str, entity_id: str | None = None) -> dict:
    return {
        "kind": kind,
        "label": label,
        "state": state,
        "entity_id": entity_id,
    }


def build_nexus_presence(project_id: int) -> dict:
    snapshot = build_nexus_snapshot(project_id)
    counts = snapshot.get("counts") or {}
    overall = str(snapshot.get("overall_state") or "ready")

    action_center = build_nexus_action_center(project_id, limit=20)
    actions = list(action_center.get("actions") or [])
    waiting = [
        item for item in actions if item.get("state") == "waiting_permission"
    ]
    recovering = [
        item for item in actions if item.get("state") == "recovery"
    ]
    failed_actions = [
        item for item in actions if item.get("state") == "error"
    ]
    active = [
        item
        for item in actions
        if item.get("state") in {"planned", "running", "verifying"}
    ]

    knowledge_attention = int(counts.get("knowledge_attention") or 0)
    failed_tasks = int(counts.get("failed_tasks") or 0)

    reasons: list[dict] = []
    if recovering:
        item = recovering[0]
        reasons.append(
            _reason(
                "workflow",
                str(item.get("title") or "Workflow требует восстановления"),
                state="recovery",
                entity_id=str(item.get("id") or ""),
            )
        )
    if waiting:
        item = waiting[0]
        reasons.append(
            _reason(
                "permission",
                str(item.get("title") or "Действие ждёт разрешения"),
                state="waiting_permission",
                entity_id=str(item.get("id") or ""),
            )
        )
    if failed_actions:
        item = failed_actions[0]
        reasons.append(
            _reason(
                "action",
                str(item.get("title") or "Действие завершилось ошибкой"),
                state="error",
                entity_id=str(item.get("id") or ""),
            )
        )
    if failed_tasks:
        reasons.append(
            _reason(
                "task",
                f"Фоновых задач с ошибкой: {failed_tasks}",
                state="error",
            )
        )
    if knowledge_attention:
        reasons.append(
            _reason(
                "knowledge",
                f"Элементов знаний для проверки: {knowledge_attention}",
                state="background_attention",
            )
        )
    if active:
        item = active[0]
        reasons.append(
            _reason(
                "action",
                str(item.get("title") or "Выполняется действие"),
                state=str(item.get("state") or "running"),
                entity_id=str(item.get("id") or ""),
            )
        )

    if recovering:
        mode = "recovery"
        headline = "Восстанавливаю выполнение"
        detail = "Проверяю состояние прерванного действия перед безопасным продолжением."
        attention = "high"
    elif failed_actions or failed_tasks or overall == "error":
        mode = "attention"
        headline = "Нужно внимание"
        detail = "Есть ошибка выполнения. Детали сохранены в Actions/System."
        attention = "high"
    elif waiting:
        mode = "waiting"
        headline = "Жду вашего решения"
        detail = "Есть действие, которое не продолжится без явного разрешения."
        attention = "normal"
    elif active:
        active_item = active[0]
        active_state = str(active_item.get("state") or "running")
        mode = "verifying" if active_state == "verifying" else "working"
        headline = "Проверяю" if mode == "verifying" else "Работаю"
        detail = str(
            (active_item.get("progress") or {}).get("label")
            or active_item.get("title")
            or active_item.get("state_label")
            or "Выполняется реальная задача."
        )
        attention = "low"
    elif overall in {"degraded", "not_connected"}:
        mode = "degraded"
        headline = "Работаю с ограничениями"
        detail = (
            "Часть возможностей проекта сейчас ограничена."
            if overall == "degraded"
            else "Не все обязательные сервисы подключены."
        )
        attention = "low"
    else:
        mode = "ready"
        headline = "Готова"
        detail = "Нет активной работы или решений, требующих внимания."
        attention = "none"

    events = list_nexus_events(project_id, limit=1, tail=True).get("events") or []
    last_event = None
    if events:
        event = events[-1]
        last_event = {
            "id": event.get("id"),
            "event_type": event.get("event_type"),
            "severity": event.get("severity"),
            "summary": event.get("summary"),
            "created_at": event.get("created_at"),
            "source": event.get("source"),
        }

    return {
        "schema_version": NEXUS_PRESENCE_SCHEMA_VERSION,
        "project": snapshot["project"],
        "mode": mode,
        "headline": headline,
        "detail": detail,
        "attention": attention,
        "reasons": reasons[:5],
        "activity": {
            "waiting_permissions": len(waiting),
            "recovering_actions": len(recovering),
            "failed_actions": len(failed_actions),
            "active_actions": len(active),
            "failed_tasks": failed_tasks,
            "knowledge_attention": knowledge_attention,
        },
        "last_event": last_event,
        "source_contract": {
            "authoritative": True,
            "sources": [
                "nexus_snapshot",
                "nexus_actions",
                "nexus_events",
            ],
            "random_liveness_allowed": False,
            "decorative_activity_allowed": False,
        },
        "generated_at": _now(),
    }
