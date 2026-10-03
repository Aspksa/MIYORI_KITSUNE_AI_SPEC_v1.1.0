from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .db import get_project, search_document_chunks, search_verified_memory


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    irreversible: bool
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
        name="project_memory_search",
        description="Поиск только по подтверждённой памяти текущего проекта.",
        irreversible=False,
        handler=project_memory_search,
    ),
    "project_document_search": ToolSpec(
        name="project_document_search",
        description="Поиск по индексированным документам текущего проекта.",
        irreversible=False,
        handler=project_document_search,
    ),
    "project_status": ToolSpec(
        name="project_status",
        description="Чтение состояния текущего проекта.",
        irreversible=False,
        handler=project_status,
    ),
}


def list_tools() -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "irreversible": spec.irreversible,
        }
        for spec in TOOLS.values()
    ]


def execute_tool(name: str, project_id: int, arguments: dict) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        raise ValueError("Инструмент не найден.")
    if spec.irreversible:
        raise PermissionError("Необратимый инструмент требует отдельного подтверждения.")

    result = spec.handler(project_id=project_id, **arguments)
    return {"tool": name, "result": result}
