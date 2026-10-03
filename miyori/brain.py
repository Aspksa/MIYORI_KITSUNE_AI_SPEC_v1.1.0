from __future__ import annotations

from dataclasses import dataclass

from .db import search_document_chunks, verified_memory_context


@dataclass
class BrainContext:
    goal: str
    plan: list[str]
    memory: list[str]
    documents: list[dict]
    tools_allowed: list[str]


def build_plan(message: str) -> list[str]:
    text = message.strip()
    plan = ["Понять цель запроса и ограничения."]
    if len(text) > 180 or any(word in text.lower() for word in ("сравни", "проанализ", "план", "проверь")):
        plan.append("Разбить задачу на проверяемые шаги.")
    plan.append("Подобрать релевантную память и документы проекта.")
    plan.append("Сформировать ответ и проверить его на явные противоречия с контекстом.")
    return plan


def build_context(project_id: int, message: str) -> BrainContext:
    return BrainContext(
        goal=message.strip(),
        plan=build_plan(message),
        memory=verified_memory_context(project_id, message, limit=8),
        documents=search_document_chunks(project_id, message, limit=5),
        tools_allowed=["project_memory_search", "project_document_search", "project_status"],
    )
