from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import (
    connect,
    get_project,
    list_agent_workflows,
    list_audit_events,
    list_permission_requests,
    list_tasks,
    list_workflow_events,
    list_workflow_steps,
)
from .tools import list_tools


NEXUS_ACTION_SCHEMA_VERSION = "1.0.0"
NEXUS_ACTION_STATES = {
    "planned",
    "waiting_permission",
    "running",
    "verifying",
    "recovery",
    "completed",
    "error",
    "cancelled",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _tool_catalog() -> dict[str, dict]:
    return {str(item["name"]): item for item in list_tools()}


def _list_tool_operations(project_id: int, limit: int = 400) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM tool_operations
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, max(1, min(int(limit), 1000))),
        ).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["arguments"] = _loads(item.pop("arguments_json", None), {})
        item["preflight"] = _loads(item.pop("preflight_json", None), {})
        item["result"] = _loads(item.pop("result_json", None), None)
        item["error"] = _loads(item.pop("error_json", None), None)
        result.append(item)
    return result


def _task_events(task_ids: list[int]) -> dict[int, list[dict]]:
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, task_id, event_type, details, created_at
            FROM task_events
            WHERE task_id IN ({placeholders})
            ORDER BY id ASC
            """,
            task_ids,
        ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        item = dict(row)
        raw = item.get("details")
        item["details"] = _loads(raw, raw)
        grouped.setdefault(int(item["task_id"]), []).append(item)
    return grouped


def _operation_state(status: str | None) -> str:
    return {
        "planned": "planned",
        "running": "running",
        "verifying": "verifying",
        "recovery_required": "recovery",
        "executed": "completed",
        "failed": "error",
        "cancelled": "cancelled",
    }.get(str(status or ""), "planned")


def _workflow_state(workflow: dict, operations: list[dict]) -> str:
    status = str(workflow.get("status") or "")
    if status == "waiting_permission":
        return "waiting_permission"
    if status == "recovering":
        return "recovery"
    if status == "completed":
        return "completed"
    if status == "failed":
        return "error"
    if status == "cancelled":
        return "cancelled"
    if any(item.get("status") == "verifying" for item in operations):
        return "verifying"
    if status == "running":
        return "running"
    return "planned"


def _permission_state(permission: dict, operation: dict | None) -> str:
    status = str(permission.get("status") or "")
    if status == "pending":
        return "waiting_permission"
    if status == "denied":
        return "cancelled"
    if status == "failed":
        return "error"
    if status == "executed":
        return "completed"
    if operation:
        return _operation_state(operation.get("status"))
    if status == "approved":
        return "running"
    return "planned"


def _task_state(status: str | None) -> str:
    return {
        "queued": "planned",
        "running": "running",
        "completed": "completed",
        "failed": "error",
        "cancelled": "cancelled",
    }.get(str(status or ""), "planned")


def _state_label(state: str) -> str:
    return {
        "planned": "Планируется",
        "waiting_permission": "Ждёт разрешения",
        "running": "Выполняется",
        "verifying": "Проверяется",
        "recovery": "Требует восстановления",
        "completed": "Завершено",
        "error": "Ошибка",
        "cancelled": "Отменено",
    }[state]


def _history_severity(event_type: str) -> str:
    lowered = event_type.lower()
    if any(token in lowered for token in ("failed", "error")):
        return "error"
    if any(token in lowered for token in ("waiting", "permission", "recovery", "cancel")):
        return "warning"
    if any(token in lowered for token in ("completed", "executed", "approved")):
        return "success"
    return "info"


def _history_item(
    event_type: str,
    created_at: str | None,
    *,
    summary: str | None = None,
    data: Any = None,
) -> dict:
    return {
        "type": event_type,
        "summary": summary or event_type.replace(".", " · "),
        "severity": _history_severity(event_type),
        "data": data,
        "created_at": created_at,
    }


def _audit_history(events: list[dict]) -> list[dict]:
    return [
        _history_item(
            str(item.get("event_type") or "audit.event"),
            item.get("created_at"),
            summary=str(item.get("summary") or item.get("event_type") or "Событие"),
            data=item.get("details") or {},
        )
        for item in reversed(events)
    ]


def _operation_evidence(operation: dict | None, audits: list[dict] | None = None) -> list[dict]:
    if not operation:
        return []
    evidence: list[dict] = []
    preflight = operation.get("preflight") or {}
    if preflight:
        evidence.append({
            "kind": "preflight",
            "label": "Preflight",
            "status": "recorded",
            "data": preflight,
        })
    for item in audits or []:
        if item.get("event_type") == "tool.verification":
            details = item.get("details") or {}
            evidence.append({
                "kind": "verification",
                "label": "Проверка перед выполнением",
                "status": "passed" if details.get("safe_to_retry") or details.get("completed") else "checked",
                "data": details.get("verification") or details,
            })
    if operation.get("error"):
        evidence.append({
            "kind": "error",
            "label": "Ошибка операции",
            "status": "failed",
            "data": operation.get("error"),
        })
    return evidence


def _tool_meta(tool_name: str | None, catalog: dict[str, dict]) -> dict:
    item = catalog.get(str(tool_name or "")) or {}
    return {
        "name": tool_name,
        "description": item.get("description") or tool_name or "Действие",
        "category": item.get("category") or "general",
        "risk_level": item.get("risk_level") or "low",
        "destructive": bool(item.get("destructive")),
        "idempotent": bool(item.get("idempotent", True)),
        "rollback_capability": item.get("rollback_capability") or "none",
        "recovery_strategy": item.get("recovery_strategy") or "verify_only",
    }


def _controls(
    *,
    state: str,
    permission_id: int | None = None,
    workflow_id: int | None = None,
    task_id: int | None = None,
) -> dict:
    return {
        "approve_permission": permission_id if state == "waiting_permission" else None,
        "deny_permission": permission_id if state == "waiting_permission" else None,
        "recover_workflow": workflow_id if state == "recovery" else None,
        "cancel_workflow": (
            workflow_id
            if workflow_id is not None and state in {"planned", "waiting_permission", "running", "verifying"}
            else None
        ),
        "cancel_task": (
            task_id if task_id is not None and state in {"planned", "running"} else None
        ),
        "check_recovery": state == "recovery" and workflow_id is None,
    }


def _workflow_card(
    workflow: dict,
    *,
    permissions: list[dict],
    operations: list[dict],
    audits: list[dict],
    catalog: dict[str, dict],
) -> dict:
    workflow_id = int(workflow["id"])
    steps = list_workflow_steps(workflow_id)
    events = list_workflow_events(workflow_id, limit=200)
    workflow_permissions = [
        item for item in permissions if item.get("workflow_id") == workflow_id
    ]
    pending = next(
        (item for item in workflow_permissions if item.get("status") == "pending"),
        None,
    )
    workflow_operations = [
        item for item in operations if item.get("workflow_id") == workflow_id
    ]
    latest_operation = workflow_operations[0] if workflow_operations else None
    state = _workflow_state(workflow, workflow_operations)
    tool_name = (
        (pending or {}).get("tool_name")
        or (latest_operation or {}).get("tool_name")
        or next(
            (
                step.get("tool_name")
                for step in reversed(steps)
                if step.get("tool_name")
            ),
            None,
        )
    )
    meta = _tool_meta(tool_name, catalog)
    preview = (pending or {}).get("preview")
    if not preview and workflow_permissions:
        preview = workflow_permissions[0].get("preview")

    operation_audits = [
        item
        for item in audits
        if item.get("workflow_id") == workflow_id
        and item.get("event_type") == "tool.verification"
    ]
    history = [
        _history_item(
            str(item.get("event_type") or "workflow.event"),
            item.get("created_at"),
            data=item.get("payload") or {},
        )
        for item in events
    ]
    completed_steps = sum(
        1 for item in steps if item.get("status") in {"completed", "skipped"}
    )
    progress = {
        "current_step": int(workflow.get("current_step") or 0),
        "completed_steps": completed_steps,
        "step_count": len(steps),
        "max_steps": int(workflow.get("max_steps") or 0),
        "label": (
            f"Шаг {int(workflow.get('current_step') or 0)} · "
            f"завершено {completed_steps} · бюджет {int(workflow.get('max_steps') or 0)}"
        ),
    }
    current_step = next(
        (
            item for item in reversed(steps)
            if int(item.get("step_index") or -1) == int(workflow.get("current_step") or 0)
        ),
        steps[-1] if steps else None,
    )
    summary = (
        (preview or {}).get("summary")
        or (current_step or {}).get("reason")
        or str(workflow.get("goal") or "Workflow")
    )
    permission_id = int(pending["id"]) if pending else None
    return {
        "id": f"workflow:{workflow_id}",
        "kind": "workflow",
        "state": state,
        "state_label": _state_label(state),
        "title": str(workflow.get("goal") or f"Workflow #{workflow_id}"),
        "summary": summary,
        "project_id": int(workflow["project_id"]),
        "workflow_id": workflow_id,
        "task_id": None,
        "permission_id": permission_id,
        "operation_id": (latest_operation or {}).get("id"),
        "tool": meta,
        "preview": preview,
        "progress": progress,
        "steps": [
            {
                "id": int(item["id"]),
                "index": int(item.get("step_index") or 0),
                "kind": item.get("kind"),
                "tool_name": item.get("tool_name"),
                "reason": item.get("reason"),
                "status": item.get("status"),
                "argument_keys": sorted((item.get("arguments") or {}).keys()),
                "result": item.get("result"),
                "retry_count": int(item.get("retry_count") or 0),
                "created_at": item.get("created_at"),
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
            }
            for item in steps
        ],
        "evidence": _operation_evidence(latest_operation, operation_audits),
        "result": workflow.get("result"),
        "error": workflow.get("error") or (latest_operation or {}).get("error"),
        "controls": _controls(
            state=state,
            permission_id=permission_id,
            workflow_id=workflow_id,
        ),
        "history": history,
        "created_at": workflow.get("created_at"),
        "updated_at": workflow.get("updated_at") or workflow.get("created_at"),
        "finished_at": workflow.get("finished_at"),
    }


def _permission_card(
    permission: dict,
    *,
    operation: dict | None,
    audits: list[dict],
    catalog: dict[str, dict],
) -> dict:
    permission_id = int(permission["id"])
    state = _permission_state(permission, operation)
    tool_name = str(permission.get("tool_name") or (operation or {}).get("tool_name") or "")
    meta = _tool_meta(tool_name, catalog)
    preview = permission.get("preview") or None
    relevant_audits = [
        item
        for item in audits
        if item.get("entity_type") == "permission"
        and str(item.get("entity_id")) == str(permission_id)
    ]
    operation_audits = [
        item
        for item in audits
        if operation
        and item.get("entity_type") == "tool_operation"
        and str(item.get("entity_id")) == str(operation.get("id"))
    ]
    return {
        "id": f"permission:{permission_id}",
        "kind": "tool",
        "state": state,
        "state_label": _state_label(state),
        "title": str(meta["description"]),
        "summary": (
            (preview or {}).get("summary")
            or permission.get("reason")
            or str(meta["description"])
        ),
        "project_id": int(permission["project_id"]),
        "workflow_id": None,
        "task_id": None,
        "permission_id": permission_id,
        "operation_id": (operation or {}).get("id"),
        "tool": meta,
        "preview": preview,
        "progress": None,
        "steps": [],
        "evidence": _operation_evidence(operation, operation_audits),
        "result": permission.get("result") or (operation or {}).get("result"),
        "error": (operation or {}).get("error"),
        "controls": _controls(state=state, permission_id=permission_id),
        "history": _audit_history(relevant_audits + operation_audits),
        "created_at": permission.get("created_at"),
        "updated_at": (
            permission.get("executed_at")
            or permission.get("decided_at")
            or (operation or {}).get("updated_at")
            or permission.get("created_at")
        ),
        "finished_at": permission.get("executed_at"),
    }


def _operation_card(
    operation: dict,
    *,
    audits: list[dict],
    catalog: dict[str, dict],
) -> dict:
    operation_id = int(operation["id"])
    state = _operation_state(operation.get("status"))
    meta = _tool_meta(operation.get("tool_name"), catalog)
    relevant_audits = [
        item
        for item in audits
        if item.get("entity_type") == "tool_operation"
        and str(item.get("entity_id")) == str(operation_id)
    ]
    return {
        "id": f"operation:{operation_id}",
        "kind": "tool",
        "state": state,
        "state_label": _state_label(state),
        "title": str(meta["description"]),
        "summary": str(meta["description"]),
        "project_id": int(operation["project_id"]),
        "workflow_id": None,
        "task_id": None,
        "permission_id": operation.get("permission_request_id"),
        "operation_id": operation_id,
        "tool": meta,
        "preview": None,
        "progress": None,
        "steps": [],
        "evidence": _operation_evidence(operation, relevant_audits),
        "result": operation.get("result"),
        "error": operation.get("error"),
        "controls": _controls(state=state),
        "history": _audit_history(relevant_audits),
        "created_at": operation.get("created_at"),
        "updated_at": operation.get("updated_at") or operation.get("created_at"),
        "finished_at": operation.get("finished_at"),
    }


def _task_card(task: dict, history: list[dict]) -> dict:
    task_id = int(task["id"])
    state = _task_state(task.get("status"))
    return {
        "id": f"task:{task_id}",
        "kind": "task",
        "state": state,
        "state_label": _state_label(state),
        "title": str(task.get("task_type") or f"Задача #{task_id}"),
        "summary": (
            "Отмена запрошена; задача завершит текущую безопасную точку."
            if task.get("cancel_requested")
            else "Фоновая задача проекта."
        ),
        "project_id": int(task["project_id"]),
        "workflow_id": None,
        "task_id": task_id,
        "permission_id": None,
        "operation_id": None,
        "tool": None,
        "preview": None,
        "progress": None,
        "steps": [],
        "evidence": [],
        "result": task.get("result"),
        "error": task.get("result") if state == "error" else None,
        "controls": _controls(state=state, task_id=task_id),
        "history": [
            _history_item(
                str(item.get("event_type") or "task.event"),
                item.get("created_at"),
                data=item.get("details"),
            )
            for item in history
        ],
        "created_at": task.get("created_at"),
        "updated_at": task.get("finished_at") or task.get("started_at") or task.get("created_at"),
        "finished_at": task.get("finished_at"),
    }


def build_nexus_action_center(project_id: int, *, limit: int = 60) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")

    limit = max(1, min(int(limit), 200))
    catalog = _tool_catalog()
    permissions = list_permission_requests(project_id, limit=200)
    workflows = list_agent_workflows(project_id, limit=200)
    tasks = list_tasks(project_id, limit=200)
    operations = _list_tool_operations(project_id, limit=600)
    audits = list_audit_events(project_id, limit=500)

    operations_by_id = {int(item["id"]): item for item in operations}
    task_history = _task_events([int(item["id"]) for item in tasks])
    cards: list[dict] = []
    covered_permission_ids: set[int] = set()
    covered_operation_ids: set[int] = set()

    for workflow in workflows:
        workflow_id = int(workflow["id"])
        workflow_permissions = [
            item for item in permissions if item.get("workflow_id") == workflow_id
        ]
        workflow_operations = [
            item for item in operations if item.get("workflow_id") == workflow_id
        ]
        covered_permission_ids.update(int(item["id"]) for item in workflow_permissions)
        covered_operation_ids.update(int(item["id"]) for item in workflow_operations)
        cards.append(
            _workflow_card(
                workflow,
                permissions=permissions,
                operations=operations,
                audits=audits,
                catalog=catalog,
            )
        )

    for permission in permissions:
        permission_id = int(permission["id"])
        if permission_id in covered_permission_ids:
            continue
        operation = (
            operations_by_id.get(int(permission["tool_operation_id"]))
            if permission.get("tool_operation_id")
            else None
        )
        if operation:
            covered_operation_ids.add(int(operation["id"]))
        cards.append(
            _permission_card(
                permission,
                operation=operation,
                audits=audits,
                catalog=catalog,
            )
        )

    for operation in operations:
        operation_id = int(operation["id"])
        if operation_id in covered_operation_ids:
            continue
        cards.append(_operation_card(operation, audits=audits, catalog=catalog))

    for task in tasks:
        task_id = int(task["id"])
        cards.append(_task_card(task, task_history.get(task_id, [])))

    priority = {
        "waiting_permission": 0,
        "recovery": 1,
        "error": 2,
        "verifying": 3,
        "running": 4,
        "planned": 5,
        "completed": 6,
        "cancelled": 7,
    }
    cards.sort(
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
        reverse=True,
    )
    cards.sort(key=lambda item: priority.get(str(item.get("state")), 99))

    counts = {state: 0 for state in sorted(NEXUS_ACTION_STATES)}
    for item in cards:
        counts[str(item["state"])] += 1
    counts.update({
        "attention": counts["waiting_permission"] + counts["recovery"] + counts["error"],
        "active": counts["planned"] + counts["running"] + counts["verifying"],
        "history": counts["completed"] + counts["cancelled"],
        "total": len(cards),
        "returned": min(len(cards), limit),
    })
    cards = cards[:limit]

    return {
        "schema_version": NEXUS_ACTION_SCHEMA_VERSION,
        "project": {
            "id": int(project["id"]),
            "name": project["name"],
            "kind": project.get("kind"),
        },
        "counts": counts,
        "actions": cards,
        "generated_at": _now(),
        "semantics": {
            "authoritative_sources": [
                "agent_workflows",
                "workflow_steps",
                "permission_requests",
                "tool_operations",
                "tasks",
                "workflow_events",
                "task_events",
                "audit_events",
            ],
            "permission_embedded_in_workflow": True,
            "speculative_progress_allowed": False,
        },
    }
