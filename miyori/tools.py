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
    create_document_folder,
    get_document,
    get_document_chunks,
    get_document_folder_parts,
    list_document_folders,
    list_documents,
    move_document_record,
)
from .db import get_project
from .documents import ensure_drive_folder, move_active_document, safe_folder_name
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
    parameters: dict[str, Any] | None = None


def project_memory_search(project_id: int, query: str) -> dict:
    return {"facts": search_verified_memory(project_id, query, limit=12)}


def project_document_search(project_id: int, query: str) -> dict:
    return {"chunks": search_document_chunks(project_id, query, limit=12)}


def project_status(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")
    return {"project": project, "status": "ready"}


def project_document_catalog(project_id: int) -> dict:
    documents = [
        {
            "id": item["id"],
            "folder_id": item.get("folder_id"),
            "filename": item["filename"],
            "mime_type": item.get("mime_type"),
            "size_bytes": item.get("size_bytes"),
            "chunk_count": item.get("chunk_count", 0),
            "created_at": item.get("created_at"),
        }
        for item in list_documents(project_id)
    ]
    folders = [
        {
            "id": item["id"],
            "parent_id": item.get("parent_id"),
            "name": item["name"],
            "document_count": item.get("document_count", 0),
        }
        for item in list_document_folders(project_id)
    ]
    return {"documents": documents[:500], "folders": folders[:500]}


def project_document_read(
    project_id: int,
    document_id: int,
    start: int = 0,
    limit: int = 12,
) -> dict:
    document = get_document(project_id, int(document_id))
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")
    chunks = get_document_chunks(
        project_id,
        int(document_id),
        start=int(start),
        limit=int(limit),
    )
    return {
        "document": {
            "id": document["id"],
            "filename": document["filename"],
            "mime_type": document.get("mime_type"),
            "size_bytes": document.get("size_bytes"),
            "chunk_count": document.get("chunk_count", 0),
        },
        "chunks": chunks,
    }


def drive_folder_create(
    project_id: int,
    name: str,
    parent_id: int | None = None,
) -> dict:
    clean = safe_folder_name(name)
    parent_parts = get_document_folder_parts(project_id, parent_id)
    ensure_drive_folder(project_id, [*parent_parts, clean])
    folder = create_document_folder(project_id, clean, parent_id=parent_id)
    return {"folder": folder}


def drive_document_move(
    project_id: int,
    document_id: int,
    folder_id: int | None = None,
) -> dict:
    document = get_document(project_id, int(document_id))
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")

    target_parts = get_document_folder_parts(project_id, folder_id)
    old_parts = get_document_folder_parts(project_id, document.get("folder_id"))
    old_path = document["stored_path"]

    new_path = move_active_document(
        project_id,
        old_path,
        document["filename"],
        target_parts,
    )
    try:
        updated = move_document_record(
            project_id,
            int(document_id),
            folder_id,
            new_path,
        )
        if not updated:
            raise ValueError("Не удалось обновить запись документа.")
    except Exception:
        # Best-effort rollback keeps filesystem and DB aligned if DB update fails.
        try:
            move_active_document(
                project_id,
                new_path,
                document["filename"],
                old_parts,
            )
        except Exception:
            pass
        raise
    return {"document": updated}


TOOLS: dict[str, ToolSpec] = {
    "project_memory_search": ToolSpec(
        "project_memory_search",
        "Поиск только по подтверждённой памяти текущего проекта.",
        "read",
        project_memory_search,
        {"query": {"type": "string", "required": True}},
    ),
    "project_document_search": ToolSpec(
        "project_document_search",
        "Поиск по индексированным документам текущего проекта.",
        "read",
        project_document_search,
        {"query": {"type": "string", "required": True}},
    ),
    "project_status": ToolSpec(
        "project_status",
        "Чтение состояния текущего проекта.",
        "read",
        project_status,
    ),
    "project_document_catalog": ToolSpec(
        "project_document_catalog",
        "Каталог активных документов и папок только текущего проекта.",
        "read",
        project_document_catalog,
    ),
    "project_document_read": ToolSpec(
        "project_document_read",
        "Чтение индексированных фрагментов конкретного документа текущего проекта по document_id.",
        "read",
        project_document_read,
        {
            "document_id": {"type": "integer", "required": True},
            "start": {"type": "integer", "required": False, "default": 0},
            "limit": {"type": "integer", "required": False, "default": 12},
        },
    ),
    "drive_folder_create": ToolSpec(
        "drive_folder_create",
        "Создание папки в Miyori Drive текущего проекта. Требует подтверждения.",
        "write",
        drive_folder_create,
        {
            "name": {"type": "string", "required": True},
            "parent_id": {"type": "integer|null", "required": False, "default": None},
        },
    ),
    "drive_document_move": ToolSpec(
        "drive_document_move",
        "Перемещение оригинала документа между папками Miyori Drive текущего проекта. Требует подтверждения.",
        "write",
        drive_document_move,
        {
            "document_id": {"type": "integer", "required": True},
            "folder_id": {"type": "integer|null", "required": False, "default": None},
        },
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
        {"path": {"type": "string", "required": True}},
    ),
    "workspace_create": ToolSpec(
        "workspace_create",
        "Создание нового UTF-8 файла в рабочей папке проекта.",
        "write",
        create_workspace_file,
        {
            "path": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        },
    ),
    "workspace_modify": ToolSpec(
        "workspace_modify",
        "Изменение существующего UTF-8 файла в рабочей папке проекта.",
        "write",
        modify_workspace_file,
        {
            "path": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        },
    ),
}


def list_tools() -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "permission": spec.permission,
            "requires_confirmation": spec.permission != "read",
            "parameters": spec.parameters or {},
        }
        for spec in TOOLS.values()
    ]


def _validate_tool_arguments(spec: ToolSpec, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("Аргументы инструмента должны быть объектом.")

    schema = spec.parameters or {}
    unexpected = set(arguments) - set(schema)
    if unexpected:
        raise ValueError(
            "Неизвестные аргументы инструмента: " + ", ".join(sorted(unexpected))
        )

    normalized = dict(arguments)
    for key, rule in schema.items():
        required = bool(rule.get("required", False))
        if key not in normalized:
            if required:
                raise ValueError(f"Не указан обязательный аргумент: {key}.")
            if "default" in rule:
                normalized[key] = rule["default"]
            continue

        value = normalized[key]
        expected = rule.get("type")
        if expected == "string" and not isinstance(value, str):
            raise ValueError(f"Аргумент {key} должен быть строкой.")
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"Аргумент {key} должен быть целым числом.")
        if expected == "integer|null" and value is not None and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ValueError(f"Аргумент {key} должен быть целым числом или null.")

    return normalized


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

    arguments = _validate_tool_arguments(spec, arguments)

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
