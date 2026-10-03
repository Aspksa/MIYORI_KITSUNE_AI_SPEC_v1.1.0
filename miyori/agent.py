from __future__ import annotations

from dataclasses import dataclass

from .context_router import ContextRoute
from .db import finish_agent_run, record_agent_action, start_agent_run
from .planner import (
    MAX_AGENT_STEPS,
    fallback_decision,
    parse_planner_payload,
    planner_prompt,
)
from .provider import ProviderError, plan_next_action
from .tools import execute_tool, list_tools


@dataclass
class AgentResult:
    run_id: int
    actions: list[dict]
    tool_context: list[dict]
    planner_mode: str
    pending_permissions: list[dict]


def _public_action(
    *,
    tool: str | None,
    status: str,
    reason: str,
    result: dict | None = None,
) -> dict:
    return {
        "tool": tool,
        "status": status,
        "reason": reason,
        "result": result or {},
    }


async def run_agent(
    project_id: int,
    conversation_id: int | None,
    message: str,
    route: ContextRoute,
    conversation_context: list[dict[str, str]] | None = None,
) -> AgentResult:
    run_id = start_agent_run(
        project_id,
        conversation_id,
        message,
        MAX_AGENT_STEPS,
    )
    actions: list[dict] = []
    planner_history: list[dict] = []
    tool_context: list[dict] = []
    pending_permissions: list[dict] = []
    planner_mode = "not_needed"
    executed_signatures: set[str] = set()

    try:
        if not route.use_tools:
            action = record_agent_action(
                run_id=run_id,
                step_index=0,
                reason="Context Router не обнаружил необходимости в инструментах.",
                status="skipped",
            )
            actions.append(action)
            finish_agent_run(run_id, "completed")
            return AgentResult(
                run_id=run_id,
                actions=actions,
                tool_context=[],
                planner_mode=planner_mode,
                pending_permissions=[],
            )

        tool_catalog = list_tools()
        allowed_tools = {item["name"] for item in tool_catalog}
        planner_mode = "model"
        planner_available = True

        for step_index in range(1, MAX_AGENT_STEPS + 1):
            if planner_available:
                try:
                    payload = await plan_next_action(
                        planner_prompt(
                            message,
                            route,
                            tool_catalog,
                            planner_history,
                            conversation_context=conversation_context,
                        )
                    )
                    decision = parse_planner_payload(payload, allowed_tools)
                except (ProviderError, ValueError, TypeError):
                    planner_available = False
                    planner_mode = "fallback"
                    decision = fallback_decision(
                        message,
                        route,
                        planner_history,
                    )
            else:
                decision = fallback_decision(
                    message,
                    route,
                    planner_history,
                )

            if decision.action == "finish":
                action = record_agent_action(
                    run_id=run_id,
                    step_index=step_index,
                    reason=decision.reason,
                    status="completed",
                )
                actions.append(action)
                break

            tool_name = decision.tool_name or ""
            signature = tool_name + ":" + repr(sorted(decision.arguments.items()))
            if signature in executed_signatures:
                action = record_agent_action(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name=tool_name,
                    reason="Planner попытался повторить то же действие; цикл остановлен.",
                    arguments=decision.arguments,
                    result={"duplicate_action": True},
                    status="skipped",
                )
                actions.append(action)
                break
            executed_signatures.add(signature)

            try:
                execution = execute_tool(
                    tool_name,
                    project_id,
                    decision.arguments,
                    reason=decision.reason,
                )
                execution_status = execution.get("status", "executed")

                if execution_status == "approval_required":
                    permission_request = execution.get("permission_request") or {}
                    result = {
                        "approval_required": True,
                        "permission_request_id": permission_request.get("id"),
                        "tool_name": tool_name,
                    }
                    action_status = "approval_required"
                    pending_permissions.append(permission_request)
                    tool_context.append(
                        {
                            "tool": tool_name,
                            "reason": decision.reason,
                            "result": result,
                        }
                    )
                else:
                    result = execution.get("result") or {}
                    action_status = "completed"
                    tool_context.append(
                        {
                            "tool": tool_name,
                            "reason": decision.reason,
                            "result": result,
                        }
                    )

                action = record_agent_action(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name=tool_name,
                    reason=decision.reason,
                    arguments=decision.arguments,
                    result=result,
                    status=action_status,
                )
                actions.append(action)
                planner_history.append(
                    _public_action(
                        tool=tool_name,
                        status=execution_status,
                        reason=decision.reason,
                        result=result,
                    )
                )

                # A pending write must be resolved by the existing permission UI
                # before a dependent write plan can continue safely.
                if execution_status == "approval_required":
                    break

            except Exception as exc:
                error_result = {"error": str(exc)}
                action = record_agent_action(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name=tool_name,
                    reason=decision.reason,
                    arguments=decision.arguments,
                    result=error_result,
                    status="failed",
                )
                actions.append(action)
                planner_history.append(
                    _public_action(
                        tool=tool_name,
                        status="failed",
                        reason=decision.reason,
                        result=error_result,
                    )
                )

        finish_agent_run(run_id, "completed")
        return AgentResult(
            run_id=run_id,
            actions=actions,
            tool_context=tool_context,
            planner_mode=planner_mode,
            pending_permissions=pending_permissions,
        )
    except Exception:
        finish_agent_run(run_id, "failed")
        raise
