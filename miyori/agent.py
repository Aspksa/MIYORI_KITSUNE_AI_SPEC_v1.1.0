from __future__ import annotations

from dataclasses import dataclass, field

from .db import (
    finish_agent_run,
    record_agent_action,
    start_agent_run,
)
from .tools import execute_tool


MAX_AGENT_STEPS = 3


@dataclass
class AgentDecision:
    tool_name: str | None
    reason: str
    arguments: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    run_id: int
    actions: list[dict]
    tool_context: list[dict]


def decide_actions(message: str) -> list[AgentDecision]:
    text = message.strip()
    lowered = text.lower()
    actions: list[AgentDecision] = []

    memory_markers = (
        "помни", "памят", "я говорил", "я предпочитаю", "мой ", "моя ", "мои ",
    )
    document_markers = (
        "документ", "файл", "источник", "найди", "прочитай", "по материал",
        "в тексте", "в проекте", "спецификац",
    )
    status_markers = (
        "статус проекта", "состояние проекта", "готов ли проект", "проверь проект",
    )

    if any(marker in lowered for marker in status_markers):
        actions.append(
            AgentDecision(
                tool_name="project_status",
                reason="Запрос относится к текущему состоянию проекта.",
            )
        )

    if any(marker in lowered for marker in memory_markers):
        actions.append(
            AgentDecision(
                tool_name="project_memory_search",
                reason="Запрос может зависеть от подтверждённой памяти проекта.",
                arguments={"query": text},
            )
        )

    if any(marker in lowered for marker in document_markers):
        actions.append(
            AgentDecision(
                tool_name="project_document_search",
                reason="Запрос может зависеть от материалов и документов проекта.",
                arguments={"query": text},
            )
        )

    return actions[:MAX_AGENT_STEPS]


def run_agent(project_id: int, conversation_id: int | None, message: str) -> AgentResult:
    run_id = start_agent_run(project_id, conversation_id, message, MAX_AGENT_STEPS)
    actions: list[dict] = []
    tool_context: list[dict] = []

    try:
        decisions = decide_actions(message)
        if not decisions:
            actions.append(
                record_agent_action(
                    run_id=run_id,
                    step_index=0,
                    reason="Дополнительный инструмент не требуется: базовый контекст уже подобран Brain.",
                    status="skipped",
                )
            )
            finish_agent_run(run_id, "completed")
            return AgentResult(run_id=run_id, actions=actions, tool_context=[])

        for index, decision in enumerate(decisions, start=1):
            if index > MAX_AGENT_STEPS:
                break

            try:
                execution = execute_tool(
                    decision.tool_name or "",
                    project_id,
                    decision.arguments,
                )
                action = record_agent_action(
                    run_id=run_id,
                    step_index=index,
                    tool_name=decision.tool_name,
                    reason=decision.reason,
                    arguments=decision.arguments,
                    result=execution["result"],
                    status="completed",
                )
                tool_context.append(
                    {
                        "tool": decision.tool_name,
                        "reason": decision.reason,
                        "result": execution["result"],
                    }
                )
            except Exception as exc:
                action = record_agent_action(
                    run_id=run_id,
                    step_index=index,
                    tool_name=decision.tool_name,
                    reason=decision.reason,
                    arguments=decision.arguments,
                    result={"error": str(exc)},
                    status="failed",
                )
            actions.append(action)

        finish_agent_run(run_id, "completed")
        return AgentResult(run_id=run_id, actions=actions, tool_context=tool_context)
    except Exception:
        finish_agent_run(run_id, "failed")
        raise
