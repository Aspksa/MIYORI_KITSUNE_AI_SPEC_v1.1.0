from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .agent import cancel_agent_workflow, run_agent
from .context_router import route_context
from .db import (
    connect,
    create_task,
    get_agent_workflow,
    get_project,
    record_audit_event,
    utc_now,
)
from .planner import MAX_AGENT_STEPS


NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION = "1.0.0"
WORKSPACE_STATUSES = {
    "planned",
    "running",
    "waiting_permission",
    "recovery",
    "completed",
    "failed",
    "cancelled",
}
NODE_STATUSES = {
    "blocked",
    "ready",
    "running",
    "waiting_permission",
    "recovery",
    "completed",
    "failed",
    "cancelled",
}
MAX_WORKSPACE_NODES = 8
MAX_PARALLEL_NODES = 3
MAX_WORKSPACE_STEPS = 24


def init_agent_workspace_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'planned','running','waiting_permission','recovery',
                    'completed','failed','cancelled'
                )),
                max_parallel INTEGER NOT NULL DEFAULT 2,
                total_step_budget INTEGER NOT NULL DEFAULT 12,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_workspace_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                node_key TEXT NOT NULL,
                role TEXT NOT NULL,
                title TEXT NOT NULL,
                instruction TEXT NOT NULL,
                capability TEXT NOT NULL DEFAULT 'read_only' CHECK(capability IN ('read_only','standard')),
                dependencies_json TEXT NOT NULL DEFAULT '[]',
                step_budget INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL CHECK(status IN (
                    'blocked','ready','running','waiting_permission',
                    'recovery','completed','failed','cancelled'
                )),
                workflow_id INTEGER,
                result_json TEXT,
                error_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                UNIQUE(workspace_id, node_key),
                FOREIGN KEY(workspace_id) REFERENCES agent_workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_agent_workspaces_project
                ON agent_workspaces(project_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_agent_workspace_nodes
                ON agent_workspace_nodes(workspace_id, id ASC);
            """
        )
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(agent_workspace_nodes)").fetchall()
        }
        if "capability" not in columns:
            conn.execute(
                "ALTER TABLE agent_workspace_nodes ADD COLUMN capability TEXT NOT NULL DEFAULT 'read_only'"
            )


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _node_row(row: Any) -> dict:
    item = dict(row)
    item["dependencies"] = list(_loads(item.pop("dependencies_json", None), []))
    item["result"] = _loads(item.pop("result_json", None), None)
    item["error"] = _loads(item.pop("error_json", None), None)
    return item


def _workspace_row(row: Any) -> dict:
    item = dict(row)
    item["max_parallel"] = int(item.get("max_parallel") or 1)
    item["total_step_budget"] = int(item.get("total_step_budget") or 0)
    return item


def _validate_node_specs(nodes: list[dict]) -> list[dict]:
    if not nodes or len(nodes) > MAX_WORKSPACE_NODES:
        raise ValueError(f"Agent Workspace должен содержать 1–{MAX_WORKSPACE_NODES} узлов.")

    normalized: list[dict] = []
    keys: set[str] = set()
    total_budget = 0
    for index, raw in enumerate(nodes):
        key = str(raw.get("key") or f"node_{index + 1}").strip()[:64]
        if not key or key in keys:
            raise ValueError("node key должен быть непустым и уникальным.")
        keys.add(key)
        role = str(raw.get("role") or "agent").strip()[:80]
        title = str(raw.get("title") or role).strip()[:160]
        capability = str(raw.get("capability") or "read_only").strip()
        if capability not in {"read_only", "standard"}:
            raise ValueError(f"Недопустимая capability узла {key}.")
        instruction = str(raw.get("instruction") or "").strip()
        if not instruction:
            raise ValueError(f"Для узла {key} нужна инструкция.")
        dependencies = [
            str(value).strip()
            for value in (raw.get("depends_on") or [])
            if str(value).strip()
        ]
        if key in dependencies:
            raise ValueError(f"Узел {key} не может зависеть от самого себя.")
        budget = max(1, min(int(raw.get("step_budget") or 3), MAX_AGENT_STEPS))
        total_budget += budget
        normalized.append(
            {
                "key": key,
                "role": role,
                "title": title,
                "instruction": instruction[:6000],
                "capability": capability,
                "depends_on": dependencies,
                "step_budget": budget,
            }
        )

    if total_budget > MAX_WORKSPACE_STEPS:
        raise ValueError(
            f"Суммарный budget Agent Workspace не может превышать {MAX_WORKSPACE_STEPS} шагов."
        )

    for item in normalized:
        unknown = set(item["depends_on"]) - keys
        if unknown:
            raise ValueError(
                f"Узел {item['key']} зависит от неизвестных узлов: {', '.join(sorted(unknown))}."
            )

    graph = {item["key"]: set(item["depends_on"]) for item in normalized}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in visiting:
            raise ValueError("Dependency graph содержит цикл.")
        visiting.add(key)
        for dependency in graph[key]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)

    return normalized


def default_agent_workspace_nodes(goal: str) -> list[dict]:
    clean = " ".join(goal.strip().split())
    return [
        {
            "key": "research",
            "role": "Исследователь",
            "title": "Контекст и материалы",
            "instruction": (
                "Изучи документы, материалы, память и доступные факты текущего проекта по цели: "
                f"{clean}. Ничего не изменяй; собирай только evidence и фактический контекст."
            ),
            "depends_on": [],
            "step_budget": 3,
        },
        {
            "key": "risk_review",
            "role": "Ревьюер рисков",
            "title": "Риски и противоречия",
            "capability": "read_only",
            "instruction": (
                "Проверь проект, источники и утверждения на риски, противоречия и недостающие "
                f"evidence относительно цели: {clean}. Ничего не изменяй."
            ),
            "depends_on": [],
            "step_budget": 3,
        },
        {
            "key": "coordinator",
            "role": "Координатор",
            "title": "Сведение и действия",
            "capability": "standard",
            "instruction": (
                "Сверь handoff двух предыдущих агентов и продолжи цель: "
                f"{clean}. Если требуется write-действие, используй обычный permission pipeline."
            ),
            "depends_on": ["research", "risk_review"],
            "step_budget": 5,
        },
    ]


def create_agent_workspace(
    project_id: int,
    goal: str,
    nodes: list[dict] | None = None,
    *,
    max_parallel: int = 2,
) -> dict:
    init_agent_workspace_db()
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")
    clean_goal = " ".join(goal.strip().split())
    if not clean_goal:
        raise ValueError("Нужна цель Agent Workspace.")

    specs = _validate_node_specs(nodes or default_agent_workspace_nodes(clean_goal))
    parallel = max(1, min(int(max_parallel), MAX_PARALLEL_NODES))
    total_budget = sum(int(item["step_budget"]) for item in specs)
    now = utc_now()

    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_workspaces(
                project_id, goal, status, max_parallel, total_step_budget,
                created_at, updated_at
            ) VALUES (?, ?, 'planned', ?, ?, ?, ?)
            """,
            (project_id, clean_goal[:6000], parallel, total_budget, now, now),
        )
        workspace_id = int(cur.lastrowid)
        for item in specs:
            status = "ready" if not item["depends_on"] else "blocked"
            conn.execute(
                """
                INSERT INTO agent_workspace_nodes(
                    workspace_id, node_key, role, title, instruction, capability,
                    dependencies_json, step_budget, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    item["key"],
                    item["role"],
                    item["title"],
                    item["instruction"],
                    item["capability"],
                    json.dumps(item["depends_on"], ensure_ascii=False),
                    item["step_budget"],
                    status,
                    now,
                    now,
                ),
            )

    record_audit_event(
        project_id,
        "user",
        "agent_workspace.created",
        "Создан Agent Workspace.",
        entity_type="agent_workspace",
        entity_id=workspace_id,
        details={
            "goal": clean_goal[:500],
            "nodes": [item["key"] for item in specs],
            "max_parallel": parallel,
            "total_step_budget": total_budget,
        },
    )
    return get_agent_workspace(project_id, workspace_id) or {}


def list_agent_workspaces(project_id: int, limit: int = 30) -> list[dict]:
    init_agent_workspace_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_workspaces
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_workspace_row(row) for row in rows]


def get_agent_workspace(project_id: int, workspace_id: int) -> dict | None:
    init_agent_workspace_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM agent_workspaces
            WHERE id = ? AND project_id = ?
            """,
            (workspace_id, project_id),
        ).fetchone()
        if not row:
            return None
        node_rows = conn.execute(
            """
            SELECT *
            FROM agent_workspace_nodes
            WHERE workspace_id = ?
            ORDER BY id ASC
            """,
            (workspace_id,),
        ).fetchall()

    workspace = _workspace_row(row)
    nodes = [_node_row(item) for item in node_rows]
    counts = {status: 0 for status in sorted(NODE_STATUSES)}
    for node in nodes:
        counts[str(node["status"])] += 1
    workspace["nodes"] = nodes
    workspace["counts"] = counts
    workspace["schema_version"] = NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION
    return workspace


def _update_node(
    node_id: int,
    *,
    status: str | None = None,
    workflow_id: int | None = None,
    result: dict | None = None,
    error: dict | None = None,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> None:
    fields = ["updated_at = ?"]
    values: list[Any] = [utc_now()]
    if status is not None:
        if status not in NODE_STATUSES:
            raise ValueError("Недопустимый status Agent Workspace node.")
        fields.append("status = ?")
        values.append(status)
    if workflow_id is not None:
        fields.append("workflow_id = ?")
        values.append(workflow_id)
    if result is not None:
        fields.append("result_json = ?")
        values.append(json.dumps(result, ensure_ascii=False, default=str))
    if error is not None:
        fields.append("error_json = ?")
        values.append(json.dumps(error, ensure_ascii=False, default=str))
    if mark_started:
        fields.append("started_at = COALESCE(started_at, ?)")
        values.append(utc_now())
    if mark_finished:
        fields.append("finished_at = ?")
        values.append(utc_now())
    values.append(node_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE agent_workspace_nodes SET {', '.join(fields)} WHERE id = ?",
            values,
        )


def _sync_linked_workflows(project_id: int, workspace_id: int) -> None:
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise ValueError("Agent Workspace не найден.")

    mapping = {
        "running": "running",
        "waiting_permission": "waiting_permission",
        "recovering": "recovery",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    for node in workspace["nodes"]:
        workflow_id = node.get("workflow_id")
        if not workflow_id:
            continue
        workflow = get_agent_workflow(int(workflow_id), project_id)
        if not workflow:
            _update_node(
                int(node["id"]),
                status="failed",
                error={"code": "workflow_missing"},
                mark_finished=True,
            )
            continue
        status = mapping.get(str(workflow.get("status")), "running")
        result = {
            "workflow_status": workflow.get("status"),
            "workflow_result": workflow.get("result"),
        }
        if status == "completed":
            _update_node(int(node["id"]), status=status, result=result, mark_finished=True)
        elif status in {"failed", "cancelled"}:
            _update_node(
                int(node["id"]),
                status=status,
                result=result,
                error=workflow.get("error") or {},
                mark_finished=True,
            )
        else:
            _update_node(int(node["id"]), status=status, result=result)


def _refresh_dependency_states(project_id: int, workspace_id: int) -> dict:
    _sync_linked_workflows(project_id, workspace_id)
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise ValueError("Agent Workspace не найден.")

    by_key = {str(item["node_key"]): item for item in workspace["nodes"]}
    for node in workspace["nodes"]:
        if node["status"] not in {"blocked", "ready"} or node.get("workflow_id"):
            continue
        dependencies = [by_key[key] for key in node["dependencies"]]
        if any(item["status"] in {"failed", "cancelled"} for item in dependencies):
            _update_node(
                int(node["id"]),
                status="failed",
                error={"code": "dependency_failed"},
                mark_finished=True,
            )
        elif all(item["status"] == "completed" for item in dependencies):
            _update_node(int(node["id"]), status="ready")
        else:
            _update_node(int(node["id"]), status="blocked")

    return _update_workspace_status(project_id, workspace_id)


def _update_workspace_status(project_id: int, workspace_id: int) -> dict:
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise ValueError("Agent Workspace не найден.")
    if workspace["status"] == "cancelled":
        return workspace

    statuses = [str(item["status"]) for item in workspace["nodes"]]
    if statuses and all(value == "completed" for value in statuses):
        status = "completed"
    elif any(value == "recovery" for value in statuses):
        status = "recovery"
    elif any(value == "waiting_permission" for value in statuses):
        status = "waiting_permission"
    elif any(value == "running" for value in statuses):
        status = "running"
    elif any(value == "ready" for value in statuses):
        status = "running"
    elif any(value == "failed" for value in statuses):
        status = "failed"
    else:
        status = "planned"

    fields = ["status = ?", "updated_at = ?"]
    values: list[Any] = [status, utc_now()]
    if status == "running":
        fields.append("started_at = COALESCE(started_at, ?)")
        values.append(utc_now())
    if status in {"completed", "failed", "cancelled"}:
        fields.append("finished_at = COALESCE(finished_at, ?)")
        values.append(utc_now())
    values.extend([workspace_id, project_id])
    with connect() as conn:
        conn.execute(
            f"UPDATE agent_workspaces SET {', '.join(fields)} WHERE id = ? AND project_id = ?",
            values,
        )
    return get_agent_workspace(project_id, workspace_id) or workspace


def _handoff(workspace: dict, node: dict) -> str:
    by_key = {str(item["node_key"]): item for item in workspace["nodes"]}
    parts: list[str] = []
    for key in node["dependencies"]:
        dependency = by_key.get(str(key))
        if not dependency:
            continue
        payload = dependency.get("result")
        text = json.dumps(payload, ensure_ascii=False, default=str)
        parts.append(f"{dependency['role']} / {dependency['title']}: {text[:3000]}")
    if not parts:
        return ""
    return "\n\nHandoff от завершённых узлов:\n" + "\n".join(parts)


def _run_node(project_id: int, workspace_id: int, node: dict) -> dict:
    _update_node(int(node["id"]), status="running", mark_started=True)
    current = get_agent_workspace(project_id, workspace_id)
    if not current:
        raise ValueError("Agent Workspace не найден.")
    message = (
        f"Роль: {node['role']}\n"
        f"Задача: {node['instruction']}"
        f"{_handoff(current, node)}"
    )
    request_key = f"agent-workspace:{workspace_id}:node:{node['id']}"
    try:
        result = asyncio.run(
            run_agent(
                project_id,
                None,
                message,
                route_context(message),
                [],
                request_key=request_key,
                max_steps=int(node["step_budget"]),
                tool_permissions=("read",) if node.get("capability") == "read_only" else None,
            )
        )
        workflow = get_agent_workflow(result.workflow_id, project_id) or {}
        mapped = {
            "waiting_permission": "waiting_permission",
            "recovering": "recovery",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(result.workflow_status, "running")
        payload = {
            "workflow_status": result.workflow_status,
            "planner_mode": result.planner_mode,
            "actions": result.actions,
            "tool_context": result.tool_context,
            "workflow_result": workflow.get("result"),
        }
        _update_node(
            int(node["id"]),
            status=mapped,
            workflow_id=result.workflow_id,
            result=payload,
            error=workflow.get("error") if mapped == "failed" else None,
            mark_finished=mapped in {"completed", "failed", "cancelled"},
        )
        record_audit_event(
            project_id,
            "miyori",
            "agent_workspace.node_finished",
            f"Agent Workspace node {node['node_key']} завершил текущий цикл.",
            workflow_id=result.workflow_id,
            entity_type="agent_workspace_node",
            entity_id=node["id"],
            details={
                "workspace_id": workspace_id,
                "node_key": node["node_key"],
                "status": mapped,
                "step_budget": int(node["step_budget"]),
                "capability": node.get("capability"),
            },
        )
        return {"node_id": node["id"], "status": mapped, "workflow_id": result.workflow_id}
    except Exception as exc:
        _update_node(
            int(node["id"]),
            status="failed",
            error={"type": exc.__class__.__name__, "message": str(exc)},
            mark_finished=True,
        )
        return {"node_id": node["id"], "status": "failed", "error": str(exc)}


def run_agent_workspace_cycle(project_id: int, payload: dict) -> dict:
    workspace_id = int(payload.get("workspace_id") or 0)
    if workspace_id <= 0:
        raise ValueError("Для Agent Workspace нужен workspace_id.")

    workspace = _refresh_dependency_states(project_id, workspace_id)
    if workspace["status"] in {"completed", "cancelled"}:
        return workspace

    batches: list[dict] = []
    for _ in range(MAX_WORKSPACE_NODES):
        workspace = _refresh_dependency_states(project_id, workspace_id)
        ready = [item for item in workspace["nodes"] if item["status"] == "ready"]
        if not ready:
            break

        selected = ready[: int(workspace["max_parallel"])]
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="miyori-agent") as pool:
            futures = [
                pool.submit(_run_node, project_id, workspace_id, node)
                for node in selected
            ]
            for future in as_completed(futures):
                results.append(future.result())
        batches.append({"nodes": results})

        workspace = _refresh_dependency_states(project_id, workspace_id)
        if workspace["status"] in {"waiting_permission", "recovery", "failed", "cancelled"}:
            break

    workspace = _refresh_dependency_states(project_id, workspace_id)
    return {"workspace": workspace, "batches": batches}


def enqueue_agent_workspace(project_id: int, workspace_id: int) -> dict:
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise ValueError("Agent Workspace не найден.")
    if workspace["status"] in {"completed", "cancelled"}:
        raise ValueError("Этот Agent Workspace уже завершён.")

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, task_type, status, cancel_requested,
                   payload_json, created_at, started_at, finished_at
            FROM tasks
            WHERE project_id = ?
              AND task_type = 'agent_workspace'
              AND status IN ('queued','running')
            ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()
    for row in rows:
        item = dict(row)
        payload = _loads(item.pop("payload_json", None), {})
        if int(payload.get("workspace_id") or 0) == workspace_id:
            item["cancel_requested"] = bool(item.get("cancel_requested"))
            return item

    return create_task(
        project_id,
        "agent_workspace",
        {"workspace_id": workspace_id},
    )


def cancel_agent_workspace(project_id: int, workspace_id: int) -> dict:
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise ValueError("Agent Workspace не найден.")
    if workspace["status"] == "cancelled":
        return workspace

    recovery_blocked = False
    for node in workspace["nodes"]:
        workflow_id = node.get("workflow_id")
        if workflow_id and node["status"] not in {"completed", "failed", "cancelled"}:
            try:
                asyncio.run(cancel_agent_workflow(project_id, int(workflow_id)))
            except RuntimeError:
                recovery_blocked = True
                _update_node(
                    int(node["id"]),
                    status="recovery",
                    error={"code": "cancel_deferred_until_recovery"},
                )
                continue
        if node["status"] not in {"completed", "failed", "cancelled"}:
            _update_node(
                int(node["id"]),
                status="cancelled",
                result={"outcome": "workspace_cancelled"},
                mark_finished=True,
            )

    if recovery_blocked:
        with connect() as conn:
            conn.execute(
                """
                UPDATE agent_workspaces
                SET status = 'recovery', updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (utc_now(), workspace_id, project_id),
            )
        record_audit_event(
            project_id,
            "system",
            "agent_workspace.cancel_deferred",
            "Отмена Agent Workspace отложена до завершения recovery дочернего workflow.",
            entity_type="agent_workspace",
            entity_id=workspace_id,
        )
        return get_agent_workspace(project_id, workspace_id) or workspace

    with connect() as conn:
        conn.execute(
            """
            UPDATE agent_workspaces
            SET status = 'cancelled', updated_at = ?, finished_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (utc_now(), utc_now(), workspace_id, project_id),
        )
    record_audit_event(
        project_id,
        "user",
        "agent_workspace.cancelled",
        "Пользователь остановил Agent Workspace.",
        entity_type="agent_workspace",
        entity_id=workspace_id,
    )
    return get_agent_workspace(project_id, workspace_id) or workspace
