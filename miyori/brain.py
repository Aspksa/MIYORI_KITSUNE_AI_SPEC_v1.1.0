from __future__ import annotations

from dataclasses import dataclass

from .context_router import ContextRoute


@dataclass
class BrainContext:
    goal: str
    plan: list[str]
    context_route: dict
    working_memory: str
    tools_allowed: list[str]


def build_plan(message: str, route: ContextRoute) -> list[str]:
    """Public operational plan, not hidden reasoning."""
    plan = ["Уточнить цель запроса по текущему разговору."]

    if route.use_user_memory or route.use_project_memory:
        scopes = []
        if route.use_user_memory:
            scopes.append("личную")
        if route.use_project_memory:
            scopes.append("проектную")
        plan.append("Подобрать " + " и ".join(scopes) + " подтверждённую память.")

    if route.use_documents:
        plan.append("Найти релевантные рабочие документы и точные фрагменты.")

    if route.use_epistemic:
        plan.append("Проверить уверенность, источники и возможные противоречия.")

    if route.use_tools:
        plan.append("Выполнить только разрешённые действия; изменения проводить через подтверждение.")

    plan.append("Сформировать ответ, отделив подтверждённые данные от неопределённости.")
    return plan


def build_context(
    project_id: int,
    message: str,
    route: ContextRoute,
    *,
    tools_allowed: list[str] | None = None,
) -> BrainContext:
    return BrainContext(
        goal=message.strip(),
        plan=build_plan(message, route),
        context_route=route.to_dict(),
        working_memory="recent_conversation",
        tools_allowed=tools_allowed or [],
    )
