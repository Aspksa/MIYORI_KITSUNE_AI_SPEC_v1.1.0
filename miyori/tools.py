from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Callable
from uuid import uuid4

from .db import (
    create_document_folder,
    create_permission_request,
    create_tool_operation,
    finish_permission_execution,
    get_document,
    get_document_chunks,
    get_document_folder_parts,
    get_permission_request,
    get_project,
    get_tool_operation,
    get_tool_operation_by_key,
    list_document_folders,
    list_documents,
    list_recoverable_tool_operations,
    link_tool_operation_permission,
    move_document_record,
    record_audit_event,
    record_hand_event,
    search_document_chunks,
    search_verified_memory,
    update_tool_operation,
)
from .documents import (
    ensure_drive_folder,
    move_active_document,
    project_document_dir,
    resolve_data_path,
    safe_folder_name,
)
from .hands import (
    create_workspace_file,
    list_workspace_files,
    modify_workspace_file,
    read_workspace_file,
    resolve_workspace_path,
)


RISK_LEVELS = {"low", "medium", "high"}
ROLLBACK_CAPABILITIES = {"none", "best_effort", "automatic"}
RECOVERY_STRATEGIES = {"verify_only", "verify_then_retry", "manual_review"}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: str
    handler: Callable[..., Any]
    parameters: dict[str, Any]
    version: str = "1.0"
    category: str = "general"
    risk_level: str = "low"
    destructive: bool = False
    idempotent: bool = True
    timeout_seconds: int = 15
    rollback_capability: str = "none"
    recovery_strategy: str = "verify_only"
    preview_builder: Callable[[int, dict, dict], dict] | None = None
    preflight_handler: Callable[[int, dict], dict] | None = None
    verify_handler: Callable[[int, dict, dict], dict] | None = None


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
    target = project_document_dir(project_id).joinpath(*parent_parts, clean)
    existed_before = target.exists()
    ensure_drive_folder(project_id, [*parent_parts, clean])
    try:
        folder = create_document_folder(project_id, clean, parent_id=parent_id)
    except Exception:
        if not existed_before:
            try:
                target.rmdir()
            except OSError:
                pass
        raise
    return {"folder": folder}


def drive_document_move(
    project_id: int,
    document_id: int,
    folder_id: int | None = None,
) -> dict:
    document = get_document(project_id, int(document_id))
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")

    if document.get("folder_id") == folder_id:
        return {"document": document, "already_in_target": True}

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
        try:
            rollback_path = move_active_document(
                project_id,
                new_path,
                document["filename"],
                old_parts,
            )
            move_document_record(
                project_id,
                int(document_id),
                document.get("folder_id"),
                rollback_path,
            )
        except Exception:
            pass
        raise
    return {"document": updated}


def _folder_by_name(
    project_id: int,
    name: str,
    parent_id: int | None,
) -> dict | None:
    for folder in list_document_folders(project_id):
        if (
            folder["name"].casefold() == name.casefold()
            and folder.get("parent_id") == parent_id
        ):
            return folder
    return None


def _preflight_folder_create(project_id: int, args: dict) -> dict:
    name = safe_folder_name(args["name"])
    parent_id = args.get("parent_id")
    parent_parts = get_document_folder_parts(project_id, parent_id)
    existing = _folder_by_name(project_id, name, parent_id)
    if existing:
        raise ValueError("Папка с таким названием уже существует.")
    return {
        "name": name,
        "parent_id": parent_id,
        "parent_parts": parent_parts,
        "expected_relative_path": "/".join([*parent_parts, name]),
    }


def _verify_folder_create(project_id: int, args: dict, preflight: dict) -> dict:
    name = preflight.get("name") or safe_folder_name(args["name"])
    parent_id = preflight.get("parent_id")
    folder = _folder_by_name(project_id, name, parent_id)
    parts = [*(preflight.get("parent_parts") or []), name]
    path = project_document_dir(project_id).joinpath(*parts)
    completed = bool(folder and path.is_dir())
    return {
        "completed": completed,
        "safe_to_retry": not completed,
        "result": {"folder": folder} if completed else None,
        "state": {
            "database_record": bool(folder),
            "physical_folder": path.is_dir(),
        },
    }


def _preview_folder_create(project_id: int, args: dict, preflight: dict) -> dict:
    parent = "/".join(preflight.get("parent_parts") or []) or "Мои файлы"
    return {
        "title": "Создать папку Miyori Drive",
        "summary": f"Создать папку «{preflight['name']}» в «{parent}».",
        "changes": [
            {"field": "Папка", "value": preflight["name"]},
            {"field": "Расположение", "value": parent},
        ],
        "destructive": False,
        "reversible": True,
    }


def _preflight_document_move(project_id: int, args: dict) -> dict:
    document = get_document(project_id, int(args["document_id"]))
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")
    target_id = args.get("folder_id")
    target_parts = get_document_folder_parts(project_id, target_id)
    source_parts = get_document_folder_parts(project_id, document.get("folder_id"))
    return {
        "document_id": int(document["id"]),
        "filename": document["filename"],
        "source_folder_id": document.get("folder_id"),
        "source_parts": source_parts,
        "source_stored_path": document["stored_path"],
        "target_folder_id": target_id,
        "target_parts": target_parts,
    }


def _verify_document_move(project_id: int, args: dict, preflight: dict) -> dict:
    document = get_document(project_id, int(preflight["document_id"]))
    if not document:
        return {
            "completed": False,
            "safe_to_retry": False,
            "conflict": "Документ больше не существует в активном проекте.",
        }
    target_id = preflight.get("target_folder_id")
    source_id = preflight.get("source_folder_id")
    current_id = document.get("folder_id")
    physical_ok = False
    try:
        physical_ok = resolve_data_path(document["stored_path"]).is_file()
    except ValueError:
        physical_ok = False

    if current_id == target_id and physical_ok:
        return {
            "completed": True,
            "safe_to_retry": False,
            "result": {"document": document, "recovered": True},
        }
    if current_id == source_id and physical_ok:
        return {
            "completed": False,
            "safe_to_retry": True,
            "state": "source_unchanged",
        }
    return {
        "completed": False,
        "safe_to_retry": False,
        "conflict": "Документ изменил расположение после preflight; требуется ручная проверка.",
        "state": {"current_folder_id": current_id, "expected_source_folder_id": source_id},
    }


def _preview_document_move(project_id: int, args: dict, preflight: dict) -> dict:
    source = "/".join(preflight.get("source_parts") or []) or "Мои файлы"
    target = "/".join(preflight.get("target_parts") or []) or "Мои файлы"
    return {
        "title": "Переместить документ Miyori Drive",
        "summary": f"Переместить «{preflight['filename']}» из «{source}» в «{target}».",
        "changes": [
            {"field": "Документ", "value": preflight["filename"]},
            {"field": "Откуда", "value": source},
            {"field": "Куда", "value": target},
        ],
        "destructive": False,
        "reversible": True,
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _preflight_workspace_create(project_id: int, args: dict) -> dict:
    target = resolve_workspace_path(project_id, args["path"])
    if target.exists():
        raise ValueError("Файл уже существует.")
    return {
        "path": args["path"],
        "expected_sha256": _sha256_text(args["content"]),
    }


def _verify_workspace_create(project_id: int, args: dict, preflight: dict) -> dict:
    target = resolve_workspace_path(project_id, preflight["path"])
    if not target.exists():
        return {"completed": False, "safe_to_retry": True}
    if not target.is_file():
        return {
            "completed": False,
            "safe_to_retry": False,
            "conflict": "По целевому пути появился объект, который не является файлом.",
        }
    try:
        current = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "completed": False,
            "safe_to_retry": False,
            "conflict": "Целевой файл больше не является UTF-8 текстом.",
        }
    same = _sha256_text(current) == preflight["expected_sha256"]
    return {
        "completed": same,
        "safe_to_retry": False if same else False,
        "result": {
            "path": preflight["path"],
            "size_bytes": len(current.encode("utf-8")),
            "created": True,
            "recovered": True,
        } if same else None,
        "conflict": None if same else "По целевому пути уже существует другое содержимое.",
    }


def _preflight_workspace_modify(project_id: int, args: dict) -> dict:
    target = resolve_workspace_path(project_id, args["path"])
    if not target.exists() or not target.is_file():
        raise ValueError("Файл не найден.")
    before = target.read_text(encoding="utf-8")
    return {
        "path": args["path"],
        "before_sha256": _sha256_text(before),
        "desired_sha256": _sha256_text(args["content"]),
    }


def _verify_workspace_modify(project_id: int, args: dict, preflight: dict) -> dict:
    target = resolve_workspace_path(project_id, preflight["path"])
    if not target.exists() or not target.is_file():
        return {
            "completed": False,
            "safe_to_retry": False,
            "conflict": "Исходный файл исчез после подтверждения.",
        }
    current = target.read_text(encoding="utf-8")
    current_hash = _sha256_text(current)
    if current_hash == preflight["desired_sha256"]:
        return {
            "completed": True,
            "safe_to_retry": False,
            "result": {
                "path": preflight["path"],
                "after_chars": len(current),
                "modified": True,
                "recovered": True,
            },
        }
    if current_hash == preflight["before_sha256"]:
        return {"completed": False, "safe_to_retry": True}
    return {
        "completed": False,
        "safe_to_retry": False,
        "conflict": "Файл изменился после подтверждения; автоматический повтор заблокирован.",
    }


def _preview_workspace(project_id: int, args: dict, preflight: dict) -> dict:
    action = "Создать" if "expected_sha256" in preflight else "Изменить"
    return {
        "title": f"{action} файл workspace",
        "summary": f"{action} «{args['path']}».",
        "changes": [
            {"field": "Файл", "value": args["path"]},
            {"field": "Размер нового текста", "value": len(args.get("content", ""))},
        ],
        "destructive": action == "Изменить",
        "reversible": False,
    }


TOOLS: dict[str, ToolSpec] = {
    "project_memory_search": ToolSpec(
        name="project_memory_search",
        description="Поиск по подтверждённой памяти, доступной текущему проекту.",
        permission="read",
        handler=project_memory_search,
        parameters={
            "query": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 5000, "normalize": "strip",
            },
        },
        category="memory",
    ),
    "project_document_search": ToolSpec(
        name="project_document_search",
        description="Поиск по индексированным документам только текущего проекта.",
        permission="read",
        handler=project_document_search,
        parameters={
            "query": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 5000, "normalize": "strip",
            },
        },
        category="drive",
    ),
    "project_status": ToolSpec(
        name="project_status",
        description="Чтение состояния текущего проекта.",
        permission="read",
        handler=project_status,
        parameters={},
        category="project",
    ),
    "project_document_catalog": ToolSpec(
        name="project_document_catalog",
        description="Каталог активных документов и папок только текущего проекта.",
        permission="read",
        handler=project_document_catalog,
        parameters={},
        category="drive",
    ),
    "project_document_read": ToolSpec(
        name="project_document_read",
        description="Чтение индексированных фрагментов конкретного документа текущего проекта.",
        permission="read",
        handler=project_document_read,
        parameters={
            "document_id": {
                "type": "integer", "required": True, "minimum": 1,
                "scope_entity": "document",
            },
            "start": {
                "type": "integer", "required": False, "default": 0,
                "minimum": 0, "maximum": 100000,
            },
            "limit": {
                "type": "integer", "required": False, "default": 12,
                "minimum": 1, "maximum": 40,
            },
        },
        category="drive",
    ),
    "drive_folder_create": ToolSpec(
        name="drive_folder_create",
        description="Создание папки в Miyori Drive текущего проекта.",
        permission="write",
        handler=drive_folder_create,
        parameters={
            "name": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 120, "normalize": "strip",
            },
            "parent_id": {
                "type": "integer|null", "required": False, "default": None,
                "minimum": 1, "scope_entity": "folder",
            },
        },
        category="drive",
        risk_level="low",
        destructive=False,
        idempotent=True,
        timeout_seconds=10,
        rollback_capability="best_effort",
        recovery_strategy="verify_then_retry",
        preview_builder=_preview_folder_create,
        preflight_handler=_preflight_folder_create,
        verify_handler=_verify_folder_create,
    ),
    "drive_document_move": ToolSpec(
        name="drive_document_move",
        description="Перемещение оригинала документа между папками Miyori Drive текущего проекта.",
        permission="write",
        handler=drive_document_move,
        parameters={
            "document_id": {
                "type": "integer", "required": True, "minimum": 1,
                "scope_entity": "document",
            },
            "folder_id": {
                "type": "integer|null", "required": False, "default": None,
                "minimum": 1, "scope_entity": "folder",
            },
        },
        category="drive",
        risk_level="medium",
        destructive=False,
        idempotent=True,
        timeout_seconds=15,
        rollback_capability="best_effort",
        recovery_strategy="verify_then_retry",
        preview_builder=_preview_document_move,
        preflight_handler=_preflight_document_move,
        verify_handler=_verify_document_move,
    ),
    "workspace_list": ToolSpec(
        name="workspace_list",
        description="Список файлов в изолированной рабочей папке проекта.",
        permission="read",
        handler=list_workspace_files,
        parameters={},
        category="workspace",
    ),
    "workspace_read": ToolSpec(
        name="workspace_read",
        description="Чтение UTF-8 файла из рабочей папки проекта.",
        permission="read",
        handler=read_workspace_file,
        parameters={
            "path": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 500, "normalize": "strip",
            },
        },
        category="workspace",
    ),
    "workspace_create": ToolSpec(
        name="workspace_create",
        description="Создание нового UTF-8 файла в рабочей папке проекта.",
        permission="write",
        handler=create_workspace_file,
        parameters={
            "path": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 500, "normalize": "strip",
            },
            "content": {
                "type": "string", "required": True,
                "max_length": 2_000_000,
            },
        },
        category="workspace",
        risk_level="medium",
        destructive=False,
        idempotent=True,
        timeout_seconds=15,
        rollback_capability="best_effort",
        recovery_strategy="verify_then_retry",
        preview_builder=_preview_workspace,
        preflight_handler=_preflight_workspace_create,
        verify_handler=_verify_workspace_create,
    ),
    "workspace_modify": ToolSpec(
        name="workspace_modify",
        description="Изменение существующего UTF-8 файла в рабочей папке проекта.",
        permission="write",
        handler=modify_workspace_file,
        parameters={
            "path": {
                "type": "string", "required": True,
                "min_length": 1, "max_length": 500, "normalize": "strip",
            },
            "content": {
                "type": "string", "required": True,
                "max_length": 2_000_000,
            },
        },
        category="workspace",
        risk_level="high",
        destructive=True,
        idempotent=True,
        timeout_seconds=15,
        rollback_capability="none",
        recovery_strategy="verify_then_retry",
        preview_builder=_preview_workspace,
        preflight_handler=_preflight_workspace_modify,
        verify_handler=_verify_workspace_modify,
    ),
}


def list_tools() -> list[dict]:
    return [
        {
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "category": spec.category,
            "permission": spec.permission,
            "requires_confirmation": spec.permission != "read",
            "risk_level": spec.risk_level,
            "destructive": spec.destructive,
            "idempotent": spec.idempotent,
            "timeout_seconds": spec.timeout_seconds,
            "rollback_capability": spec.rollback_capability,
            "recovery_strategy": spec.recovery_strategy,
            "parameters": spec.parameters,
        }
        for spec in TOOLS.values()
    ]


def _validate_type(key: str, value: object, expected: str) -> None:
    if expected == "string":
        ok = isinstance(value, str)
    elif expected == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "integer|null":
        ok = value is None or (isinstance(value, int) and not isinstance(value, bool))
    elif expected == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected == "boolean":
        ok = isinstance(value, bool)
    elif expected == "object":
        ok = isinstance(value, dict)
    elif expected == "array":
        ok = isinstance(value, list)
    else:
        raise ValueError(f"Неизвестный тип schema для аргумента {key}: {expected}.")
    if not ok:
        raise ValueError(f"Аргумент {key} имеет неверный тип; ожидается {expected}.")


def _validate_tool_arguments(
    spec: ToolSpec,
    project_id: int,
    arguments: dict,
) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("Аргументы инструмента должны быть объектом.")

    schema = spec.parameters
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
        expected = str(rule.get("type") or "")
        _validate_type(key, value, expected)

        if isinstance(value, str) and rule.get("normalize") == "strip":
            value = value.strip()
            normalized[key] = value

        if value is None:
            continue

        if isinstance(value, str):
            min_length = rule.get("min_length")
            max_length = rule.get("max_length")
            if min_length is not None and len(value) < int(min_length):
                raise ValueError(f"Аргумент {key} слишком короткий.")
            if max_length is not None and len(value) > int(max_length):
                raise ValueError(f"Аргумент {key} слишком длинный.")
            pattern = rule.get("pattern")
            if pattern and not re.fullmatch(str(pattern), value):
                raise ValueError(f"Аргумент {key} не соответствует допустимому формату.")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = rule.get("minimum")
            maximum = rule.get("maximum")
            if minimum is not None and value < minimum:
                raise ValueError(f"Аргумент {key} меньше допустимого значения.")
            if maximum is not None and value > maximum:
                raise ValueError(f"Аргумент {key} больше допустимого значения.")

        enum = rule.get("enum")
        if enum is not None and value not in enum:
            raise ValueError(f"Аргумент {key} имеет недопустимое значение.")

        requires = rule.get("requires") or []
        if value is not None:
            for dependency in requires:
                if dependency not in normalized or normalized.get(dependency) is None:
                    raise ValueError(
                        f"Аргумент {key} требует аргумент {dependency}."
                    )

        conflicts_with = rule.get("conflicts_with") or []
        if value is not None:
            for conflict in conflicts_with:
                if normalized.get(conflict) is not None:
                    raise ValueError(
                        f"Аргументы {key} и {conflict} нельзя использовать вместе."
                    )

        scope_entity = rule.get("scope_entity")
        if scope_entity == "document":
            if not get_document(project_id, int(value)):
                raise ValueError(f"Документ {value} не принадлежит текущему проекту.")
        elif scope_entity == "folder":
            get_document_folder_parts(project_id, int(value))

    return normalized


def _preflight(spec: ToolSpec, project_id: int, arguments: dict) -> dict:
    if not spec.preflight_handler:
        return {}
    return spec.preflight_handler(project_id, arguments)


def _preview(spec: ToolSpec, project_id: int, arguments: dict, preflight: dict) -> dict:
    if spec.preview_builder:
        return spec.preview_builder(project_id, arguments, preflight)
    return {
        "title": spec.description,
        "summary": spec.description,
        "changes": [{"field": key, "value": value} for key, value in arguments.items()],
        "destructive": spec.destructive,
        "reversible": spec.rollback_capability != "none",
    }


def _verify_operation(spec: ToolSpec, operation: dict) -> dict:
    if not spec.verify_handler:
        return {
            "completed": operation.get("status") == "executed",
            "safe_to_retry": spec.idempotent,
        }
    return spec.verify_handler(
        int(operation["project_id"]),
        operation.get("arguments") or {},
        operation.get("preflight") or {},
    )


def execute_tool(
    name: str,
    project_id: int,
    arguments: dict,
    *,
    approved: bool = False,
    reason: str | None = None,
    conversation_id: int | None = None,
    workflow_id: int | None = None,
    workflow_step_id: int | None = None,
    idempotency_key: str | None = None,
) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        raise ValueError("Инструмент не найден.")

    arguments = _validate_tool_arguments(spec, project_id, arguments)

    if spec.permission == "read":
        result = spec.handler(project_id=project_id, **arguments)
        record_hand_event(project_id, name, "execute", arguments, result)
        record_audit_event(
            project_id,
            "miyori",
            "tool.executed",
            f"Выполнен read-инструмент {name}.",
            conversation_id=conversation_id,
            workflow_id=workflow_id,
            entity_type="tool",
            entity_id=name,
            details={"arguments": arguments, "risk_level": spec.risk_level},
        )
        return {"tool": name, "status": "executed", "result": result}

    key = idempotency_key or f"manual:{name}:{uuid4().hex}"
    existing_operation = get_tool_operation_by_key(project_id, key)
    if existing_operation:
        if existing_operation.get("tool_name") != name or existing_operation.get("arguments") != arguments:
            raise ValueError("Idempotency key уже использован для другого действия.")
        if existing_operation.get("status") == "executed":
            return {
                "tool": name,
                "status": "executed",
                "result": existing_operation.get("result") or {},
                "operation_id": existing_operation["id"],
                "replayed": True,
            }
        existing_permission_id = existing_operation.get("permission_request_id")
        if existing_permission_id:
            existing_request = get_permission_request(project_id, int(existing_permission_id))
            if existing_request and existing_request.get("status") in {"pending", "approved"}:
                return {
                    "tool": name,
                    "status": "approval_required",
                    "permission_request": existing_request,
                    "operation_id": existing_operation["id"],
                    "replayed": True,
                }
            if existing_request and existing_request.get("status") == "executed":
                return {
                    "tool": name,
                    "status": "executed",
                    "result": existing_request.get("result") or {},
                    "operation_id": existing_operation["id"],
                    "replayed": True,
                }

    preflight = _preflight(spec, project_id, arguments)
    operation = create_tool_operation(
        project_id,
        name,
        key,
        arguments,
        workflow_id=workflow_id,
        workflow_step_id=workflow_step_id,
        preflight=preflight,
    )

    if approved:
        return _execute_write_operation(
            spec,
            operation,
            conversation_id=conversation_id,
        )

    preview = _preview(spec, project_id, arguments, preflight)
    request = create_permission_request(
        project_id=project_id,
        tool_name=name,
        arguments=arguments,
        reason=reason,
        workflow_id=workflow_id,
        workflow_step_id=workflow_step_id,
        tool_operation_id=int(operation["id"]),
        idempotency_key=key,
        preview=preview,
    )
    link_tool_operation_permission(int(operation["id"]), int(request["id"]))
    record_audit_event(
        project_id,
        "miyori",
        "permission.requested",
        f"Запрошено подтверждение для {name}.",
        conversation_id=conversation_id,
        workflow_id=workflow_id,
        entity_type="permission",
        entity_id=request["id"],
        details={
            "tool": name,
            "risk_level": spec.risk_level,
            "destructive": spec.destructive,
            "preview": preview,
        },
    )
    return {
        "tool": name,
        "status": "approval_required",
        "permission_request": request,
        "operation_id": operation["id"],
    }


def _execute_write_operation(
    spec: ToolSpec,
    operation: dict,
    *,
    conversation_id: int | None = None,
) -> dict:
    project_id = int(operation["project_id"])

    if operation["status"] == "executed":
        return {
            "tool": spec.name,
            "status": "executed",
            "result": operation.get("result") or {},
            "operation_id": operation["id"],
            "replayed": True,
        }

    if spec.verify_handler:
        verification = _verify_operation(spec, operation)
        if verification.get("completed"):
            result = verification.get("result") or {}
            update_tool_operation(
                int(operation["id"]),
                status="executed",
                result=result,
                error=None,
                mark_finished=True,
            )
            return {
                "tool": spec.name,
                "status": "executed",
                "result": result,
                "operation_id": operation["id"],
                "recovered": operation["status"] == "recovery_required",
                "verified_before_execute": True,
            }

        safe = bool(verification.get("safe_to_retry"))
        if not safe:
            conflict = (
                verification.get("conflict")
                or "Состояние данных изменилось после подтверждения; выполнение заблокировано."
            )
            update_tool_operation(
                int(operation["id"]),
                status="recovery_required",
                error={"message": conflict, "verification": verification},
            )
            raise RuntimeError(conflict)
        if operation["status"] == "recovery_required" and not (
            spec.idempotent and spec.recovery_strategy == "verify_then_retry"
        ):
            raise RuntimeError("Операция требует ручной проверки перед повтором.")

    update_tool_operation(
        int(operation["id"]),
        status="running",
        error=None,
        increment_attempt=True,
        mark_started=True,
    )
    try:
        result = spec.handler(
            project_id=project_id,
            **(operation.get("arguments") or {}),
        )
        update_tool_operation(
            int(operation["id"]),
            status="executed",
            result=result,
            error=None,
            mark_finished=True,
        )
        record_hand_event(
            project_id,
            spec.name,
            "execute",
            operation.get("arguments") or {},
            result,
        )
        record_audit_event(
            project_id,
            "miyori",
            "tool.executed",
            f"Выполнен write-инструмент {spec.name}.",
            conversation_id=conversation_id,
            workflow_id=operation.get("workflow_id"),
            entity_type="tool_operation",
            entity_id=operation["id"],
            details={
                "tool": spec.name,
                "risk_level": spec.risk_level,
                "destructive": spec.destructive,
                "idempotency_key": operation["idempotency_key"],
            },
        )
        return {
            "tool": spec.name,
            "status": "executed",
            "result": result,
            "operation_id": operation["id"],
            "replayed": False,
        }
    except Exception as exc:
        update_tool_operation(
            int(operation["id"]),
            status="failed",
            error={"type": exc.__class__.__name__, "message": str(exc)},
            mark_finished=True,
        )
        record_audit_event(
            project_id,
            "system",
            "tool.failed",
            f"Ошибка выполнения write-инструмента {spec.name}.",
            conversation_id=conversation_id,
            workflow_id=operation.get("workflow_id"),
            entity_type="tool_operation",
            entity_id=operation["id"],
            details={"error": str(exc)},
        )
        raise


def execute_approved_request(
    project_id: int,
    request_id: int,
    *,
    conversation_id: int | None = None,
) -> dict:
    request = get_permission_request(project_id, request_id)
    if not request:
        raise ValueError("Запрос разрешения не найден.")

    if request["status"] == "executed":
        operation = (
            get_tool_operation(int(request["tool_operation_id"]))
            if request.get("tool_operation_id")
            else get_tool_operation_by_key(project_id, request.get("idempotency_key") or "")
        )
        return {
            "tool": request["tool_name"],
            "status": "executed",
            "result": request.get("result") or (operation or {}).get("result") or {},
            "operation_id": (operation or {}).get("id"),
            "replayed": True,
        }

    if request["status"] != "approved":
        raise PermissionError("Запрос ещё не одобрен.")

    spec = TOOLS.get(request["tool_name"])
    if not spec or spec.permission == "read":
        raise ValueError("Write-инструмент для разрешения не найден.")

    operation = (
        get_tool_operation(int(request["tool_operation_id"]))
        if request.get("tool_operation_id")
        else get_tool_operation_by_key(project_id, request.get("idempotency_key") or "")
    )
    if not operation:
        preflight = _preflight(spec, project_id, request["arguments"])
        operation = create_tool_operation(
            project_id,
            spec.name,
            request.get("idempotency_key") or f"permission:{request_id}",
            request["arguments"],
            workflow_id=request.get("workflow_id"),
            workflow_step_id=request.get("workflow_step_id"),
            permission_request_id=request_id,
            preflight=preflight,
        )

    try:
        execution = _execute_write_operation(
            spec,
            operation,
            conversation_id=conversation_id,
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


def reconcile_tool_operation(
    operation_id: int,
    *,
    allow_retry: bool = False,
) -> dict:
    operation = get_tool_operation(operation_id)
    if not operation:
        raise ValueError("Tool operation не найдена.")
    spec = TOOLS.get(operation["tool_name"])
    if not spec:
        raise ValueError("Инструмент operation больше не зарегистрирован.")

    if operation["status"] == "executed":
        return {
            "operation": operation,
            "state": "executed",
            "verification": {"completed": True},
        }

    verification = _verify_operation(spec, operation)
    if verification.get("completed"):
        result = verification.get("result") or {}
        updated = update_tool_operation(
            operation_id,
            status="executed",
            result=result,
            error=None,
            mark_finished=True,
        )
        permission_id = operation.get("permission_request_id")
        if permission_id:
            finish_permission_execution(
                int(operation["project_id"]),
                int(permission_id),
                "executed",
                result,
            )
        return {
            "operation": updated,
            "state": "recovered_as_completed",
            "verification": verification,
        }

    if (
        allow_retry
        and verification.get("safe_to_retry")
        and spec.idempotent
        and spec.recovery_strategy == "verify_then_retry"
    ):
        execution = _execute_write_operation(spec, operation)
        permission_id = operation.get("permission_request_id")
        if permission_id:
            finish_permission_execution(
                int(operation["project_id"]),
                int(permission_id),
                "executed",
                execution["result"],
            )
        return {
            "operation": get_tool_operation(operation_id),
            "state": "retried",
            "execution": execution,
            "verification": verification,
        }

    update_tool_operation(
        operation_id,
        status="recovery_required",
        error={
            "message": verification.get("conflict")
            or "Требуется ручная проверка перед повтором.",
        },
    )
    return {
        "operation": get_tool_operation(operation_id),
        "state": "recovery_required",
        "verification": verification,
    }


def reconcile_recoverable_operations(
    project_id: int | None = None,
    *,
    allow_retry: bool = False,
) -> dict:
    recovered = 0
    retried = 0
    manual = 0
    failures = 0
    items = []
    for operation in list_recoverable_tool_operations(project_id):
        try:
            result = reconcile_tool_operation(
                int(operation["id"]),
                allow_retry=allow_retry,
            )
            items.append(result)
            if result["state"] == "recovered_as_completed":
                recovered += 1
            elif result["state"] == "retried":
                retried += 1
            elif result["state"] == "recovery_required":
                manual += 1
        except Exception as exc:
            failures += 1
            items.append({
                "operation_id": operation["id"],
                "state": "error",
                "error": str(exc),
            })
    return {
        "checked": len(items),
        "recovered": recovered,
        "retried": retried,
        "manual_review": manual,
        "failures": failures,
        "items": items,
    }
