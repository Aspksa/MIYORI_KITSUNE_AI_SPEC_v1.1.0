from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .db import (
    create_permission_request,
    get_permission_request,
    record_hand_event,
    search_document_chunks,
    search_verified_memory,
    finish_permission_execution,
)
from .db import get_project
from .hands import (
    create_workspace_file,
    list_workspace_files,
    modify_workspace_file,
    read_workspace_file,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: str
    handler: Callable[..., Any]


def project_memory_search(project_id: int, query: str) -> dict:
    return {"facts": search_verified_memory(project_id, query, limit=12)}


def project_document_search(project_id: int, query: str) -> dict:
    return {"chunks": search_document_chunks(project_id, query, limit=12)}


def project_status(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")
    return {"project": project, "status": "ready"}


TOOLS: dict[str, ToolSpec] = {
    "project_memory_search": ToolSpec(
        "project_memory_search",
        "Поиск только по подтверждённой памяти текущего проекта.",
        "read",
        project_memory_search,
    ),
    "project_document_search": ToolSpec(
        "project_document_search",
        "Поиск по индексированным документам текущего проекта.",
        "read",
        project_document_search,
    ),
    "project_status": ToolSpec(
        "project_status",
        "Чтение состояния текущего проекта.",
        "read",
        project_status,
    ),
    "workspace_list": ToolSpec(
        "workspace_list",
        "Список файлов в изолированной рабочей папке проекта.",
        "read",
        list_workspace_files,
    ),
    "workspace_read": ToolSpec(
        "workspace_read",
        "Чтение UTF-8 файла из рабочей папки проекта.",
        "read",
        read_workspace_file,
    ),
    "workspace_create": ToolSpec(
        "workspace_create",
        "Создание нового UTF-8 файла в рабочей папке проекта.",
        "write",
        create_workspace_file,
    ),
    "workspace_modify": ToolSpec(
        "workspace_modify",
        "Изменение существующего UTF-8 файла в рабочей папке проекта.",
        "write",
        modify_workspace_file,
    ),
}


def list_tools() -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "permission": spec.permission,
            "requires_confirmation": spec.permission != "read",
        }
        for spec in TOOLS.values()
    ]


def execute_tool(
    name: str,
    project_id: int,
    arguments: dict,
    *,
    approved: bool = False,
    reason: str | None = None,
) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        raise ValueError("Инструмент не найден.")

    if spec.permission != "read" and not approved:
        request = create_permission_request(
            project_id=project_id,
            tool_name=name,
            arguments=arguments,
            reason=reason,
        )
        return {
            "tool": name,
            "status": "approval_required",
            "permission_request": request,
        }

    result = spec.handler(project_id=project_id, **arguments)
    record_hand_event(project_id, name, "execute", arguments, result)
    return {"tool": name, "status": "executed", "result": result}


def execute_approved_request(project_id: int, request_id: int) -> dict:
    request = get_permission_request(project_id, request_id)
    if not request:
        raise ValueError("Запрос разрешения не найден.")
    if request["status"] != "approved":
        raise PermissionError("Запрос ещё не одобрен.")

    try:
        execution = execute_tool(
            request["tool_name"],
            project_id,
            request["arguments"],
            approved=True,
            reason=request.get("reason"),
        )
        finish_permission_execution(
            project_id,
            request_id,
            "executed",
            execution["result"],
        )
        return execution
    except Exception as exc:
        finish_permission_execution(
            project_id,
            request_id,
            "failed",
            {"error": str(exc)},
        )
        raise
