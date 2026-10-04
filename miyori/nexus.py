from __future__ import annotations

from datetime import datetime, timezone

from .config import settings
from .db import (
    development_snapshot,
    get_project,
    list_agent_workflows,
    list_documents,
    list_memory_facts,
    list_permission_requests,
    list_tasks,
)
from .document_intelligence import document_intelligence_status
from .epistemic import epistemic_snapshot
from .tasks import worker_status

NEXUS_SCHEMA_VERSION = "1.0.0"
NEXUS_UI_CONTRACT_VERSION = "1.0.0"
NEXUS_OPERATIONAL_STATES = {
    "disabled",
    "not_connected",
    "ready",
    "processing",
    "degraded",
    "error",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _module(
    module_id: str,
    label: str,
    state: str,
    *,
    operation: str | None = None,
    last_result: str | None = None,
    limitation: str | None = None,
    updated_at: str,
) -> dict:
    if state not in NEXUS_OPERATIONAL_STATES:
        raise ValueError(f"Недопустимое NEXUS-состояние: {state}")
    return {
        "id": module_id,
        "label": label,
        "state": state,
        "operation": operation,
        "last_result": last_result,
        "limitation": limitation,
        "updated_at": updated_at,
    }


def _overall_state(modules: list[dict]) -> str:
    core_ids = {
        "ai",
        "memory",
        "documents",
        "agents",
        "background",
        "epistemic",
    }
    states = {
        item["state"]
        for item in modules
        if item.get("id") in core_ids
    }
    for state in ("error", "degraded", "processing", "not_connected"):
        if state in states:
            return state
    return "ready"


def build_nexus_snapshot(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")

    generated_at = _now()
    documents = list_documents(project_id)
    memory = list_memory_facts(project_id)
    permissions = list_permission_requests(project_id)
    tasks = list_tasks(project_id)
    workflows = list_agent_workflows(project_id, limit=200)
    development = development_snapshot(project_id)
    document_status = document_intelligence_status(project_id)
    epistemic = epistemic_snapshot(project_id)
    worker = worker_status()

    verified_memory = [item for item in memory if item.get("status") == "verified"]
    pending_permissions = [item for item in permissions if item.get("status") == "pending"]
    active_tasks = [item for item in tasks if item.get("status") in {"queued", "running"}]
    failed_tasks = [item for item in tasks if item.get("status") == "failed"]
    active_workflows = [
        item
        for item in workflows
        if item.get("status") in {"running", "waiting_permission", "recovering"}
    ]
    recovering_workflows = [
        item for item in workflows if item.get("status") == "recovering"
    ]
    waiting_workflows = [
        item for item in workflows if item.get("status") == "waiting_permission"
    ]
    standalone_pending_permissions = [
        item for item in pending_permissions if not item.get("workflow_id")
    ]
    active_actions = (
        len(active_workflows)
        + len(active_tasks)
        + len(standalone_pending_permissions)
    )
    attention_actions = (
        len(waiting_workflows)
        + len(recovering_workflows)
        + len(standalone_pending_permissions)
        + len(failed_tasks)
    )

    suggestions = []
    if pending_permissions:
        suggestions.append({
            "kind": "permission",
            "label": "Решить ожидающие действия",
            "detail": f"Ожидают решения: {len(pending_permissions)}",
        })
    if active_tasks:
        suggestions.append({
            "kind": "tasks",
            "label": "Проверить активные задачи",
            "detail": f"В работе или очереди: {len(active_tasks)}",
        })
    if failed_tasks:
        suggestions.append({
            "kind": "failed_tasks",
            "label": "Разобрать ошибки задач",
            "detail": f"Ошибок: {len(failed_tasks)}",
        })
    if documents:
        suggestions.append({
            "kind": "documents",
            "label": "Работать с материалами проекта",
            "detail": f"Документов: {len(documents)}",
        })
    if not suggestions:
        suggestions.append({
            "kind": "start",
            "label": "Начать новую задачу",
            "detail": "Опишите цель своими словами.",
        })

    provider_configured = bool(
        settings.cloudru_api_key and settings.cloudru_model_id
    )
    intelligence_counts = document_status.get("counts") or {}
    extraction_counts = document_status.get("extraction_counts") or {}
    documents_processing = int(intelligence_counts.get("queued", 0)) + int(
        intelligence_counts.get("analyzing", 0)
    )
    documents_limited = sum(
        int(extraction_counts.get(key, 0))
        for key in ("partial", "text_only", "needs_ocr", "unavailable")
    ) + int(intelligence_counts.get("failed", 0))
    memory_disputed = sum(
        1 for item in memory if item.get("status") == "disputed"
    )
    memory_conflicts = sum(
        1 for item in memory if item.get("possible_conflict_ids")
    )
    epistemic_claims = epistemic.get("claims") or {}
    epistemic_open_contradictions = int(
        epistemic.get("open_contradictions") or 0
    )
    knowledge_attention = (
        memory_disputed
        + memory_conflicts
        + documents_limited
        + int(epistemic_claims.get("disputed") or 0)
        + epistemic_open_contradictions
    )

    modules = [
        _module(
            "ai",
            "ИИ",
            "ready" if provider_configured else "not_connected",
            operation="configured" if provider_configured else None,
            last_result=(
                f"Модель настроена: {settings.cloudru_model_id}"
                if provider_configured
                else "Cloud.ru не настроен."
            ),
            limitation=(
                "NEXUS snapshot не выполняет сетевой health-check; фактическая доступность "
                "подтверждается тестом Cloud.ru или реальным запросом."
                if provider_configured
                else "Для генерации ответа требуется настроить Cloud.ru."
            ),
            updated_at=generated_at,
        ),
        _module(
            "memory",
            "Память",
            "ready",
            last_result=(
                f"Проверено фактов: {len(verified_memory)} · всего записей: {len(memory)}"
            ),
            limitation="Частные факты изолированы областью проекта/пользователя.",
            updated_at=generated_at,
        ),
        _module(
            "documents",
            "Документы",
            (
                "processing"
                if documents_processing
                else "degraded"
                if documents_limited
                else "ready"
            ),
            operation=(
                f"Анализируются документы: {documents_processing}"
                if documents_processing
                else None
            ),
            last_result=(
                f"Документов: {len(documents)} · extraction coverage: "
                f"{float(document_status.get('average_extraction_coverage') or 0.0):.0%}"
            ),
            limitation=(
                "Есть документы с неполным извлечением/OCR или ошибками анализа."
                if documents_limited
                else None
            ),
            updated_at=generated_at,
        ),
        _module(
            "agents",
            "Agents",
            "degraded" if recovering_workflows else "processing" if active_workflows else "ready",
            operation=(
                f"Активных workflow: {len(active_workflows)}"
                if active_workflows
                else None
            ),
            last_result=f"Workflow в recovery: {len(recovering_workflows)}",
            limitation="Write-действия проходят permission/preflight/verify контур.",
            updated_at=generated_at,
        ),
        _module(
            "background",
            "Фоновые задачи",
            "degraded" if failed_tasks else "processing" if active_tasks else "ready",
            operation=(
                f"Активных задач: {len(active_tasks)}"
                if active_tasks
                else None
            ),
            last_result=f"Ошибок задач: {len(failed_tasks)}",
            limitation=(
                "Фоновая работа выполняется только пока запущен процесс Miyori."
                if worker.get("enabled")
                else "Фоновые задачи отключены в настройках."
            ),
            updated_at=generated_at,
        ),
        _module(
            "epistemic",
            "Проверка знаний",
            "ready",
            last_result=(
                f"Источников: {int(epistemic.get('sources') or 0)} · "
                f"утверждений: {sum(int(v) for v in (epistemic.get('claims') or {}).values())}"
            ),
            limitation="Статус знания определяется свидетельствами, а не уверенностью модели.",
            updated_at=generated_at,
        ),
        _module(
            "home",
            "Home",
            "ready" if project.get("kind") == "home" else "disabled",
            last_result=(
                "Домашний проект активен."
                if project.get("kind") == "home"
                else "Home-контур не активен для рабочего проекта."
            ),
            limitation="Сетевое обнаружение устройств пока не является частью NEXUS Foundation.",
            updated_at=generated_at,
        ),
        _module(
            "voice",
            "Voice",
            "not_connected",
            last_result="Voice runtime не подключён.",
            limitation="Микрофон/STT/TTS будут подключаться отдельным capability-слоем.",
            updated_at=generated_at,
        ),
        _module(
            "desktop",
            "Desktop",
            "disabled",
            last_result="Текущий клиент — локальный web UI/launcher.",
            limitation="Desktop shell будет добавляться поверх API без замены backend-контрактов.",
            updated_at=generated_at,
        ),
        _module(
            "generative_ui",
            "Generative UI",
            "disabled",
            last_result="Определён typed surface contract; модель не получает право генерировать HTML.",
            limitation="Компонентный renderer будет подключён после стабилизации NEXUS state/event слоя.",
            updated_at=generated_at,
        ),
    ]

    counts = {
        "documents": len(documents),
        "verified_memory": len(verified_memory),
        "pending_permissions": len(pending_permissions),
        "active_tasks": len(active_tasks),
        "active_workflows": len(active_workflows),
        "recovering_workflows": len(recovering_workflows),
        "active_actions": active_actions,
        "attention_actions": attention_actions,
        "knowledge_attention": knowledge_attention,
        "memory_disputed": memory_disputed,
        "memory_conflicts": memory_conflicts,
        "failed_tasks": len(failed_tasks),
        "checks_passed": development.get("checks_passed", 0),
        "checks_total": development.get("checks_total", 0),
    }

    return {
        "schema_version": NEXUS_SCHEMA_VERSION,
        "project": project,
        "counts": counts,
        "suggestions": suggestions[:3],
        "epistemic": epistemic,
        "modules": modules,
        "overall_state": _overall_state(modules),
        "generated_at": generated_at,
        "ui_contract": {
            "version": NEXUS_UI_CONTRACT_VERSION,
            "state_source": "server_snapshot",
            "model_html_allowed": False,
            "allowed_surface_kinds": [
                "status",
                "progress",
                "action",
                "source",
                "collection",
            ],
        },
    }
