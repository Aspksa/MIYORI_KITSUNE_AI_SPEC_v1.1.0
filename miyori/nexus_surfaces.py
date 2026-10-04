from __future__ import annotations

from datetime import datetime, timezone

from .nexus import build_nexus_snapshot
from .nexus_actions import build_nexus_action_center
from .nexus_knowledge import build_nexus_knowledge_center


NEXUS_SURFACE_SCHEMA_VERSION = "1.0.0"
NEXUS_SURFACE_KINDS = {"status", "progress", "action", "source", "collection"}
NEXUS_SURFACE_COMPONENTS = {
    "status_summary",
    "action_card",
    "progress_card",
    "knowledge_attention",
    "result_collection",
}
NEXUS_SURFACE_CONTEXTS = {"auto", "chat", "actions", "knowledge", "system"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _surface(
    *,
    surface_id: str,
    kind: str,
    component: str,
    title: str,
    description: str,
    tone: str = "neutral",
    priority: int = 50,
    data: dict | None = None,
    actions: list[dict] | None = None,
) -> dict:
    if kind not in NEXUS_SURFACE_KINDS:
        raise ValueError("Недопустимый kind NEXUS surface.")
    if component not in NEXUS_SURFACE_COMPONENTS:
        raise ValueError("Недопустимый component NEXUS surface.")
    return {
        "schema_version": NEXUS_SURFACE_SCHEMA_VERSION,
        "id": surface_id,
        "kind": kind,
        "component": component,
        "title": title,
        "description": description,
        "tone": tone,
        "priority": int(priority),
        "data": data or {},
        "actions": actions or [],
        "policy": {
            "model_html_allowed": False,
            "script_allowed": False,
            "trusted_component_only": True,
            "interrupts_chat": False,
        },
    }


def _navigation(label: str, target: str) -> dict:
    return {
        "id": f"navigate:{target}",
        "type": "navigate",
        "label": label,
        "target": target,
    }


def build_nexus_surfaces(
    project_id: int,
    *,
    context: str = "auto",
    query: str = "",
    limit: int = 3,
) -> dict:
    context = str(context or "auto").strip().lower()
    if context not in NEXUS_SURFACE_CONTEXTS:
        raise ValueError("Недопустимый NEXUS surface context.")
    clean_query = " ".join(str(query or "").strip().split())[:300]
    limit = max(1, min(int(limit), 8))

    snapshot = build_nexus_snapshot(project_id)
    surfaces: list[dict] = []

    overall = str(snapshot.get("overall_state") or "ready")
    if overall in {"error", "degraded", "not_connected"}:
        tone = "error" if overall == "error" else "warning"
        surfaces.append(
            _surface(
                surface_id=f"system:{overall}",
                kind="status",
                component="status_summary",
                title="Состояние Miyori",
                description={
                    "error": "Есть ошибка, которую стоит проверить.",
                    "degraded": "Часть возможностей сейчас ограничена.",
                    "not_connected": "Не все обязательные сервисы подключены.",
                }[overall],
                tone=tone,
                priority=5,
                data={
                    "state": overall,
                    "counts": {
                        "failed_tasks": int(snapshot["counts"].get("failed_tasks") or 0),
                        "recovering_workflows": int(
                            snapshot["counts"].get("recovering_workflows") or 0
                        ),
                    },
                },
                actions=[_navigation("Открыть систему", "system")],
            )
        )

    if context in {"auto", "chat", "actions"}:
        center = build_nexus_action_center(project_id, limit=20)
        actions = list(center.get("actions") or [])
        attention = [
            item
            for item in actions
            if item.get("state") in {"waiting_permission", "recovery", "error"}
        ]
        active = [
            item
            for item in actions
            if item.get("state") in {"planned", "running", "verifying"}
        ]

        if attention:
            item = attention[0]
            tool = item.get("tool") or {}
            surfaces.append(
                _surface(
                    surface_id=f"action:{item['id']}",
                    kind="action",
                    component="action_card",
                    title=str(item.get("title") or "Действие требует внимания"),
                    description=str(item.get("summary") or ""),
                    tone=(
                        "error"
                        if item.get("state") == "error"
                        else "warning"
                    ),
                    priority=10,
                    data={
                        "state": item.get("state"),
                        "state_label": item.get("state_label"),
                        "kind": item.get("kind"),
                        "risk_level": tool.get("risk_level"),
                        "destructive": bool(tool.get("destructive")),
                        "workflow_id": item.get("workflow_id"),
                        "permission_id": item.get("permission_id"),
                    },
                    actions=[_navigation("Открыть действия", "actions")],
                )
            )
        elif active:
            item = active[0]
            surfaces.append(
                _surface(
                    surface_id=f"progress:{item['id']}",
                    kind="progress",
                    component="progress_card",
                    title=str(item.get("title") or "Действие выполняется"),
                    description=str(item.get("summary") or ""),
                    tone="working",
                    priority=30,
                    data={
                        "state": item.get("state"),
                        "state_label": item.get("state_label"),
                        "progress": item.get("progress"),
                    },
                    actions=[_navigation("Посмотреть выполнение", "actions")],
                )
            )

    knowledge_attention = int(snapshot["counts"].get("knowledge_attention") or 0)
    if context in {"auto", "chat", "knowledge"} and (clean_query or knowledge_attention > 0):
        knowledge = build_nexus_knowledge_center(
            project_id,
            query=clean_query,
            limit=30,
        )
        counts = knowledge.get("counts") or {}
        attention = counts.get("attention") or {}
        results = knowledge.get("results") or {}

        title = (
            f"Результаты по «{clean_query}»"
            if clean_query
            else "Знания требуют проверки"
        )
        description = (
            "Результаты сохранены раздельно по памяти, документам и проверяемым утверждениям."
            if clean_query
            else "Есть конфликтующие или ограниченно извлечённые данные."
        )
        surfaces.append(
            _surface(
                surface_id=(
                    f"knowledge:query:{clean_query.casefold()}"
                    if clean_query
                    else "knowledge:attention"
                ),
                kind="collection",
                component=(
                    "result_collection" if clean_query else "knowledge_attention"
                ),
                title=title,
                description=description,
                tone="warning" if int(attention.get("total") or 0) else "neutral",
                priority=20 if knowledge_attention else 40,
                data={
                    "query": clean_query,
                    "results": {
                        "memory": int(results.get("memory") or 0),
                        "documents": int(results.get("documents") or 0),
                        "claims": int(results.get("claims") or 0),
                    },
                    "attention": {
                        "total": int(attention.get("total") or 0),
                        "memory_disputed": int(attention.get("memory_disputed") or 0),
                        "memory_conflicts": int(attention.get("memory_conflicts") or 0),
                        "documents_limited": int(attention.get("documents_limited") or 0),
                        "claim_disputed": int(attention.get("claim_disputed") or 0),
                        "claim_open_contradictions": int(
                            attention.get("claim_open_contradictions") or 0
                        ),
                    },
                },
                actions=[_navigation("Открыть знания", "knowledge")],
            )
        )

    surfaces.sort(key=lambda item: (int(item["priority"]), str(item["id"])))
    selected = surfaces[:limit]

    return {
        "schema_version": NEXUS_SURFACE_SCHEMA_VERSION,
        "project": snapshot["project"],
        "context": context,
        "query": clean_query,
        "surfaces": selected,
        "registry": {
            "allowed_kinds": sorted(NEXUS_SURFACE_KINDS),
            "allowed_components": sorted(NEXUS_SURFACE_COMPONENTS),
            "model_html_allowed": False,
            "script_allowed": False,
            "unknown_components_rejected": True,
        },
        "generated_at": _now(),
    }
