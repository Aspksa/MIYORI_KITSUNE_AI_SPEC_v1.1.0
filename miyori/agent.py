from __future__ import annotations

from dataclasses import dataclass

from .context_router import ContextRoute
from .db import (
    create_agent_workflow,
    create_workflow_step,
    decide_permission_request,
    finish_agent_run,
    get_agent_trace,
    get_agent_workflow,
    get_agent_workflow_by_request_key,
    get_permission_request,
    get_workflow_step,
    list_workflow_steps,
    record_agent_action,
    record_audit_event,
    record_workflow_event,
    set_agent_run_status,
    start_agent_run,
    update_agent_workflow,
    update_workflow_step,
)
from .planner import (
    MAX_AGENT_STEPS,
    PlannerDecision,
    fallback_decision,
    parse_planner_payload,
    planner_prompt,
)
from .provider import ProviderError, plan_next_action
from .tools import (
    execute_approved_request,
    execute_tool,
    list_tools,
    reconcile_tool_operation,
)


@dataclass
class AgentResult:
    run_id: int
    workflow_id: int
    workflow_status: str
    actions: list[dict]
    tool_context: list[dict]
    planner_mode: str
    pending_permissions: list[dict]
    recovery_required: bool = False


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


def _route_from_workflow(workflow: dict) -> ContextRoute:
    payload = workflow.get("route") or {}
    return ContextRoute(
        use_recent_messages=bool(payload.get("use_recent_messages", True)),
        use_user_memory=bool(payload.get("use_user_memory", False)),
        use_project_memory=bool(payload.get("use_project_memory", False)),
        use_documents=bool(payload.get("use_documents", False)),
        use_epistemic=bool(payload.get("use_epistemic", False)),
        use_tools=bool(payload.get("use_tools", False)),
        max_rag_items=int(payload.get("max_rag_items", 8)),
        reasons=tuple(payload.get("reasons") or ()),
    )


def _planner_history(steps: list[dict]) -> list[dict]:
    history = []
    for step in steps:
        if step.get("kind") != "tool":
            continue
        status = step.get("status")
        mapped = {
            "completed": "executed",
            "waiting_permission": "approval_required",
            "failed": "failed",
            "cancelled": "denied",
            "recovery_required": "recovery_required",
            "skipped": "skipped",
        }.get(status, status or "unknown")
        history.append(
            _public_action(
                tool=step.get("tool_name"),
                status=mapped,
                reason=step.get("reason") or "",
                result=step.get("result") or {},
            )
        )
    return history


def _tool_context(steps: list[dict]) -> list[dict]:
    context = []
    for step in steps:
        if step.get("kind") != "tool":
            continue
        status = step.get("status")
        result = step.get("result") or {}
        if status == "completed":
            context.append({
                "tool": step.get("tool_name"),
                "reason": step.get("reason"),
                "result": result,
            })
        elif status == "waiting_permission":
            context.append({
                "tool": step.get("tool_name"),
                "reason": step.get("reason"),
                "result": {"approval_required": True, **result},
            })
        elif status == "failed":
            context.append({
                "tool": step.get("tool_name"),
                "reason": step.get("reason"),
                "result": {"failed": True, **result},
            })
        elif status == "cancelled":
            context.append({
                "tool": step.get("tool_name"),
                "reason": step.get("reason"),
                "result": {"permission_denied": True, **result},
            })
        elif status == "recovery_required":
            context.append({
                "tool": step.get("tool_name"),
                "reason": step.get("reason"),
                "result": {"recovery_required": True, **result},
            })
    return context


def _result_from_workflow(workflow: dict) -> AgentResult:
    steps = list_workflow_steps(int(workflow["id"]))
    trace = get_agent_trace(int(workflow["agent_run_id"])) or {"actions": []}
    pending = []
    pending_id = workflow.get("pending_permission_id")
    if pending_id:
        request = get_permission_request(int(workflow["project_id"]), int(pending_id))
        if request and request.get("status") in {"pending", "approved"}:
            pending.append(request)
    return AgentResult(
        run_id=int(workflow["agent_run_id"]),
        workflow_id=int(workflow["id"]),
        workflow_status=str(workflow["status"]),
        actions=trace.get("actions") or [],
        tool_context=_tool_context(steps),
        planner_mode=str(workflow.get("planner_mode") or "model"),
        pending_permissions=pending,
        recovery_required=workflow["status"] == "recovering"
        or any(step.get("status") == "recovery_required" for step in steps),
    )


def _step_signature(tool_name: str, arguments: dict) -> str:
    return tool_name + ":" + repr(sorted(arguments.items()))


def _step_idempotency_key(workflow_id: int, step_index: int, tool_name: str) -> str:
    return f"workflow:{workflow_id}:step:{step_index}:{tool_name}"


async def _continue_workflow(workflow: dict) -> AgentResult:
    workflow_id = int(workflow["id"])
    project_id = int(workflow["project_id"])
    run_id = int(workflow["agent_run_id"])
    route = _route_from_workflow(workflow)
    message = str(workflow["goal"])
    conversation_context = workflow.get("conversation_context") or []

    steps = list_workflow_steps(workflow_id)
    planner_history = _planner_history(steps)
    executed_signatures = {
        _step_signature(step["tool_name"], step.get("arguments") or {})
        for step in steps
        if step.get("kind") == "tool" and step.get("tool_name")
    }
    tool_permissions = workflow.get("route", {}).get("_tool_permissions")
    allowed_permissions = (
        {str(value) for value in tool_permissions}
        if isinstance(tool_permissions, list) and tool_permissions
        else None
    )
    tool_catalog = [
        item
        for item in list_tools()
        if allowed_permissions is None or str(item.get("permission")) in allowed_permissions
    ]
    allowed_tools = {item["name"] for item in tool_catalog}
    planner_mode = str(workflow.get("planner_mode") or "model")
    planner_available = planner_mode != "fallback"

    current_step = max(
        [int(workflow.get("current_step") or 0)]
        + [int(step["step_index"]) for step in steps]
    )

    if not route.use_tools and not steps:
        finish_step = create_workflow_step(
            workflow_id,
            0,
            "finish",
            "Context Router не обнаружил необходимости в инструментах.",
            status="completed",
            idempotency_key=f"workflow:{workflow_id}:finish:0",
        )
        record_agent_action(
            run_id=run_id,
            step_index=0,
            reason=finish_step["reason"],
            status="skipped",
        )
        update_agent_workflow(
            workflow_id,
            status="completed",
            current_step=0,
            pending_permission_id=None,
            result={"outcome": "no_tools_required"},
            finished=True,
        )
        finish_agent_run(run_id, "completed")
        record_workflow_event(workflow_id, "workflow.completed", {"reason": "no_tools_required"})
        return _result_from_workflow(get_agent_workflow(workflow_id) or workflow)

    for step_index in range(current_step + 1, int(workflow["max_steps"]) + 1):
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
                update_agent_workflow(workflow_id, planner_mode="fallback")
                record_workflow_event(
                    workflow_id,
                    "planner.fallback",
                    {"step_index": step_index},
                )
                decision = fallback_decision(message, route, planner_history)
        else:
            decision = fallback_decision(message, route, planner_history)

        if decision.action == "tool" and (decision.tool_name or "") not in allowed_tools:
            decision = PlannerDecision(
                action="finish",
                reason="Capability boundary не разрешает выбранный инструмент в этом workflow.",
            )

        if decision.action == "finish":
            step = create_workflow_step(
                workflow_id,
                step_index,
                "finish",
                decision.reason,
                status="completed",
                idempotency_key=f"workflow:{workflow_id}:finish:{step_index}",
            )
            action = record_agent_action(
                run_id=run_id,
                step_index=step_index,
                reason=decision.reason,
                status="completed",
            )
            update_agent_workflow(
                workflow_id,
                status="completed",
                planner_mode=planner_mode,
                current_step=step_index,
                pending_permission_id=None,
                result={"outcome": "planner_finished", "step_id": step["id"]},
                error=None,
                finished=True,
            )
            finish_agent_run(run_id, "completed")
            record_workflow_event(
                workflow_id,
                "workflow.completed",
                {"step_index": step_index, "action_id": action["id"]},
            )
            record_audit_event(
                project_id,
                "miyori",
                "workflow.completed",
                "Miyori завершила многошаговый workflow.",
                conversation_id=workflow.get("conversation_id"),
                workflow_id=workflow_id,
                entity_type="workflow",
                entity_id=workflow_id,
                details={"step_index": step_index},
            )
            return _result_from_workflow(get_agent_workflow(workflow_id) or workflow)

        tool_name = decision.tool_name or ""
        signature = _step_signature(tool_name, decision.arguments)
        if signature in executed_signatures:
            step = create_workflow_step(
                workflow_id,
                step_index,
                "tool",
                "Planner попытался повторить идентичное действие; цикл остановлен.",
                tool_name=tool_name,
                arguments=decision.arguments,
                status="skipped",
                idempotency_key=_step_idempotency_key(workflow_id, step_index, tool_name),
            )
            record_agent_action(
                run_id=run_id,
                step_index=step_index,
                tool_name=tool_name,
                reason=step["reason"],
                arguments=decision.arguments,
                result={"duplicate_action": True},
                status="skipped",
            )
            update_agent_workflow(
                workflow_id,
                status="failed",
                current_step=step_index,
                error={"code": "duplicate_action_loop"},
                finished=True,
            )
            finish_agent_run(run_id, "failed")
            record_workflow_event(workflow_id, "workflow.failed", {"code": "duplicate_action_loop"})
            record_audit_event(
                project_id,
                "system",
                "workflow.failed",
                "Workflow остановлен из-за повторяющегося действия.",
                conversation_id=workflow.get("conversation_id"),
                workflow_id=workflow_id,
                entity_type="workflow",
                entity_id=workflow_id,
                details={"code": "duplicate_action_loop"},
            )
            return _result_from_workflow(get_agent_workflow(workflow_id) or workflow)

        executed_signatures.add(signature)
        idempotency_key = _step_idempotency_key(workflow_id, step_index, tool_name)
        step = create_workflow_step(
            workflow_id,
            step_index,
            "tool",
            decision.reason,
            tool_name=tool_name,
            arguments=decision.arguments,
            status="running",
            idempotency_key=idempotency_key,
        )
        update_workflow_step(
            int(step["id"]),
            status="running",
            mark_started=True,
        )
        record_audit_event(
            project_id,
            "miyori",
            "planner.decision",
            f"Planner выбрал инструмент {tool_name}.",
            conversation_id=workflow.get("conversation_id"),
            workflow_id=workflow_id,
            entity_type="workflow_step",
            entity_id=step["id"],
            details={
                "step_index": step_index,
                "tool": tool_name,
                "reason": decision.reason,
                "argument_keys": sorted(decision.arguments.keys()),
            },
        )
        update_agent_workflow(
            workflow_id,
            status="running",
            planner_mode=planner_mode,
            current_step=step_index,
            pending_permission_id=None,
        )
        record_workflow_event(
            workflow_id,
            "tool.started",
            {"step_index": step_index, "tool": tool_name},
        )

        try:
            execution = execute_tool(
                tool_name,
                project_id,
                decision.arguments,
                reason=decision.reason,
                conversation_id=workflow.get("conversation_id"),
                workflow_id=workflow_id,
                workflow_step_id=int(step["id"]),
                idempotency_key=idempotency_key,
            )
            execution_status = execution.get("status", "executed")

            if execution_status == "approval_required":
                permission_request = execution.get("permission_request") or {}
                result = {
                    "approval_required": True,
                    "permission_request_id": permission_request.get("id"),
                    "operation_id": execution.get("operation_id"),
                    "tool_name": tool_name,
                }
                update_workflow_step(
                    int(step["id"]),
                    status="waiting_permission",
                    result=result,
                    permission_request_id=permission_request.get("id"),
                )
                record_agent_action(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name=tool_name,
                    reason=decision.reason,
                    arguments=decision.arguments,
                    result=result,
                    status="approval_required",
                )
                update_agent_workflow(
                    workflow_id,
                    status="waiting_permission",
                    planner_mode=planner_mode,
                    current_step=step_index,
                    pending_permission_id=permission_request.get("id"),
                )
                set_agent_run_status(run_id, "waiting_permission")
                record_workflow_event(
                    workflow_id,
                    "workflow.waiting_permission",
                    {
                        "step_index": step_index,
                        "permission_request_id": permission_request.get("id"),
                        "tool": tool_name,
                    },
                )
                return _result_from_workflow(get_agent_workflow(workflow_id) or workflow)

            result = execution.get("result") or {}
            update_workflow_step(
                int(step["id"]),
                status="completed",
                result=result,
                mark_finished=True,
            )
            record_agent_action(
                run_id=run_id,
                step_index=step_index,
                tool_name=tool_name,
                reason=decision.reason,
                arguments=decision.arguments,
                result=result,
                status="completed",
            )
            planner_history.append(
                _public_action(
                    tool=tool_name,
                    status="executed",
                    reason=decision.reason,
                    result=result,
                )
            )
            record_workflow_event(
                workflow_id,
                "tool.completed",
                {"step_index": step_index, "tool": tool_name},
            )

        except Exception as exc:
            error_result = {
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }
            update_workflow_step(
                int(step["id"]),
                status="failed",
                result=error_result,
                mark_finished=True,
            )
            record_agent_action(
                run_id=run_id,
                step_index=step_index,
                tool_name=tool_name,
                reason=decision.reason,
                arguments=decision.arguments,
                result=error_result,
                status="failed",
            )
            planner_history.append(
                _public_action(
                    tool=tool_name,
                    status="failed",
                    reason=decision.reason,
                    result=error_result,
                )
            )
            record_workflow_event(
                workflow_id,
                "tool.failed",
                {
                    "step_index": step_index,
                    "tool": tool_name,
                    "error": str(exc),
                },
            )

    update_agent_workflow(
        workflow_id,
        status="failed",
        planner_mode=planner_mode,
        current_step=int(workflow["max_steps"]),
        pending_permission_id=None,
        error={"code": "max_steps_exhausted"},
        finished=True,
    )
    finish_agent_run(run_id, "failed")
    record_workflow_event(workflow_id, "workflow.failed", {"code": "max_steps_exhausted"})
    record_audit_event(
        project_id,
        "system",
        "workflow.failed",
        "Workflow исчерпал допустимый бюджет шагов.",
        conversation_id=workflow.get("conversation_id"),
        workflow_id=workflow_id,
        entity_type="workflow",
        entity_id=workflow_id,
        details={"code": "max_steps_exhausted"},
    )
    return _result_from_workflow(get_agent_workflow(workflow_id) or workflow)


async def run_agent(
    project_id: int,
    conversation_id: int | None,
    message: str,
    route: ContextRoute,
    conversation_context: list[dict[str, str]] | None = None,
    *,
    request_key: str,
    max_steps: int | None = None,
    tool_permissions: tuple[str, ...] | None = None,
) -> AgentResult:
    existing = get_agent_workflow_by_request_key(project_id, request_key)
    if existing:
        return _result_from_workflow(existing)

    step_budget = max(1, min(int(max_steps or MAX_AGENT_STEPS), MAX_AGENT_STEPS))
    run_id = start_agent_run(
        project_id,
        conversation_id,
        message,
        step_budget,
    )
    route_payload = route.to_dict()
    if tool_permissions:
        normalized_permissions = sorted({str(value) for value in tool_permissions})
        invalid_permissions = set(normalized_permissions) - {"read", "write"}
        if invalid_permissions:
            raise ValueError("Недопустимое ограничение tool permissions.")
        route_payload["_tool_permissions"] = normalized_permissions

    workflow = create_agent_workflow(
        project_id=project_id,
        conversation_id=conversation_id,
        agent_run_id=run_id,
        request_key=request_key,
        goal=message,
        route=route_payload,
        conversation_context=conversation_context or [],
        max_steps=step_budget,
    )
    record_workflow_event(
        int(workflow["id"]),
        "workflow.started",
        {"request_key": request_key},
    )
    record_audit_event(
        project_id,
        "miyori",
        "workflow.started",
        "Miyori создала многошаговый workflow.",
        conversation_id=conversation_id,
        workflow_id=int(workflow["id"]),
        entity_type="workflow",
        entity_id=workflow["id"],
        details={"request_key": request_key, "goal": message[:500]},
    )
    return await _continue_workflow(workflow)


async def resume_agent_workflow(
    project_id: int,
    workflow_id: int,
    *,
    permission_request_id: int | None = None,
    recover: bool = False,
) -> AgentResult:
    workflow = get_agent_workflow(workflow_id, project_id)
    if not workflow:
        raise ValueError("Workflow не найден в текущем проекте.")
    if workflow["status"] in {"completed", "cancelled"}:
        return _result_from_workflow(workflow)

    run_id = int(workflow["agent_run_id"])

    if recover:
        steps = list_workflow_steps(workflow_id)
        for step in steps:
            step_status = step.get("status")
            if step_status not in {"recovery_required", "waiting_permission"}:
                continue

            permission_id = step.get("permission_request_id")
            if not permission_id:
                if step_status == "recovery_required":
                    update_workflow_step(
                        int(step["id"]),
                        status="failed",
                        result={"error": "Read-step interrupted by restart; planner may retry."},
                        mark_finished=True,
                    )
                continue

            request = get_permission_request(project_id, int(permission_id))
            if not request:
                update_workflow_step(
                    int(step["id"]),
                    status="failed",
                    result={"error": "Permission request lost during recovery."},
                    mark_finished=True,
                )
                continue

            if request["status"] == "approved":
                try:
                    execute_approved_request(
                        project_id,
                        int(permission_id),
                        conversation_id=workflow.get("conversation_id"),
                    )
                    request = get_permission_request(project_id, int(permission_id)) or request
                except Exception:
                    request = get_permission_request(project_id, int(permission_id)) or request

            if request["status"] == "executed":
                update_workflow_step(
                    int(step["id"]),
                    status="completed",
                    result=request.get("result") or {},
                    mark_finished=True,
                )
                continue
            if request["status"] == "denied":
                update_workflow_step(
                    int(step["id"]),
                    status="cancelled",
                    result={"permission_denied": True},
                    mark_finished=True,
                )
                continue
            if request["status"] == "failed":
                operation_id = request.get("tool_operation_id")
                if operation_id:
                    reconciliation = reconcile_tool_operation(
                        int(operation_id),
                        allow_retry=True,
                    )
                    if reconciliation.get("state") in {
                        "recovered_as_completed", "retried", "executed"
                    }:
                        refreshed = get_permission_request(
                            project_id,
                            int(permission_id),
                        )
                        update_workflow_step(
                            int(step["id"]),
                            status="completed",
                            result=(refreshed or {}).get("result") or {},
                            mark_finished=True,
                        )
                        continue
                update_workflow_step(
                    int(step["id"]),
                    status="failed",
                    result=request.get("result") or {"error": "Permission execution failed."},
                    mark_finished=True,
                )
                continue

            if request["status"] == "pending":
                update_agent_workflow(
                    workflow_id,
                    status="waiting_permission",
                    pending_permission_id=int(permission_id),
                )
                set_agent_run_status(run_id, "waiting_permission")
                return _result_from_workflow(
                    get_agent_workflow(workflow_id, project_id) or workflow
                )

        update_agent_workflow(
            workflow_id,
            status="running",
            pending_permission_id=None,
            error=None,
        )
        set_agent_run_status(run_id, "running")

    if permission_request_id is not None:
        request = get_permission_request(project_id, permission_request_id)
        if not request or int(request.get("workflow_id") or 0) != workflow_id:
            raise ValueError("Permission request не принадлежит workflow.")
        step_id = request.get("workflow_step_id")
        if not step_id:
            raise ValueError("Permission request не связан с workflow step.")
        step = get_workflow_step(int(step_id))
        if not step:
            raise ValueError("Workflow step не найден.")

        if request["status"] == "executed":
            status = "completed"
            result = request.get("result") or {}
        elif request["status"] == "denied":
            status = "cancelled"
            result = {"permission_denied": True}
        elif request["status"] == "failed":
            status = "failed"
            result = request.get("result") or {"error": "Permission execution failed."}
        elif request["status"] in {"pending", "approved"}:
            return _result_from_workflow(workflow)
        else:
            raise ValueError("Неизвестное состояние permission request.")

        update_workflow_step(
            int(step_id),
            status=status,
            result=result,
            mark_finished=True,
        )
        record_agent_action(
            run_id=run_id,
            step_index=int(step["step_index"]),
            tool_name=step.get("tool_name"),
            reason=step.get("reason") or "Результат permission.",
            arguments=step.get("arguments") or {},
            result=result,
            status=status,
        )
        record_workflow_event(
            workflow_id,
            "permission.resolved",
            {
                "permission_request_id": permission_request_id,
                "status": request["status"],
                "step_index": step["step_index"],
            },
        )
        update_agent_workflow(
            workflow_id,
            status="running",
            current_step=int(step["step_index"]),
            pending_permission_id=None,
            error=None,
        )
        set_agent_run_status(run_id, "running")

    workflow = get_agent_workflow(workflow_id, project_id) or workflow
    return await _continue_workflow(workflow)


async def cancel_agent_workflow(
    project_id: int,
    workflow_id: int,
) -> dict:
    workflow = get_agent_workflow(workflow_id, project_id)
    if not workflow:
        raise ValueError("Workflow не найден в текущем проекте.")
    if workflow["status"] == "recovering":
        raise RuntimeError("Сначала завершите проверку восстановления workflow.")
    if workflow["status"] in {"completed", "cancelled"}:
        return workflow

    permission_id = workflow.get("pending_permission_id")
    if permission_id:
        permission = get_permission_request(project_id, int(permission_id))
        if permission and permission["status"] == "pending":
            decide_permission_request(project_id, int(permission_id), False)
        if permission and permission.get("workflow_step_id"):
            step = get_workflow_step(int(permission["workflow_step_id"]))
            if step and step["status"] == "waiting_permission":
                update_workflow_step(
                    int(step["id"]),
                    status="cancelled",
                    result={"workflow_cancelled": True},
                    mark_finished=True,
                )

    update_agent_workflow(
        workflow_id,
        status="cancelled",
        pending_permission_id=None,
        result={"outcome": "cancelled_by_user"},
        error=None,
        finished=True,
    )
    set_agent_run_status(
        int(workflow["agent_run_id"]),
        "cancelled",
        finished=True,
    )
    record_workflow_event(
        workflow_id,
        "workflow.cancelled",
        {"actor": "user"},
    )
    record_audit_event(
        project_id,
        "user",
        "workflow.cancelled",
        "Пользователь остановил workflow.",
        conversation_id=workflow.get("conversation_id"),
        workflow_id=workflow_id,
        entity_type="workflow",
        entity_id=workflow_id,
    )
    return get_agent_workflow(workflow_id, project_id) or workflow
