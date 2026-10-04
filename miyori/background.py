from __future__ import annotations

import asyncio

from .agent_workspace import run_agent_workspace_cycle
from .db import list_memory_facts
from .epistemic import epistemic_snapshot, list_claims, verify_claim
from .development import run_project_self_check
from .document_intelligence import deep_analyze_document
from .document_vision import run_document_vision
from .document_questions import run_exhaustive_document_question
from .tasks import register_task_handler


def self_check_handler(project_id: int, payload: dict) -> dict:
    checks = run_project_self_check(project_id)
    return {
        "checks": [
            {"name": item.name, "passed": item.passed, "details": item.details}
            for item in checks
        ]
    }


def memory_consolidation_handler(project_id: int, payload: dict) -> dict:
    facts = list_memory_facts(project_id)
    active = [item for item in facts if item["status"] in {"candidate", "verified"}]
    conflicts = [
        {
            "fact_id": item["id"],
            "conflicts_with": item.get("possible_conflict_ids", []),
        }
        for item in active
        if item.get("possible_conflict_ids")
    ]
    return {
        "active_facts": len(active),
        "possible_conflicts": conflicts,
        "note": "Консолидация только анализирует. Статусы фактов автоматически не изменяются.",
    }


def document_intelligence_handler(project_id: int, payload: dict) -> dict:
    document_id = int(payload.get("document_id") or 0)
    if document_id <= 0:
        raise ValueError("Для Document Intelligence нужен document_id.")
    task_id = payload.get("_task_id")
    return asyncio.run(
        deep_analyze_document(
            project_id,
            document_id,
            task_id=int(task_id) if task_id is not None else None,
            force=bool(payload.get("force", False)),
        )
    )


def document_vision_handler(project_id: int, payload: dict) -> dict:
    document_id = int(payload.get("document_id") or 0)
    if document_id <= 0:
        raise ValueError("Для Vision/OCR нужен document_id.")
    task_id = payload.get("_task_id")
    return asyncio.run(
        run_document_vision(
            project_id,
            document_id,
            task_id=int(task_id) if task_id is not None else None,
            force=bool(payload.get("force", False)),
            max_items=int(payload.get("max_items") or 12),
            include_text_pages=bool(payload.get("include_text_pages", False)),
        )
    )


def document_question_handler(project_id: int, payload: dict) -> dict:
    question_id = int(payload.get("question_id") or 0)
    if question_id <= 0:
        raise ValueError("Для полного вопроса по документу нужен question_id.")
    task_id = payload.get("_task_id")
    return asyncio.run(
        run_exhaustive_document_question(
            project_id,
            question_id,
            task_id=int(task_id) if task_id is not None else None,
        )
    )


def epistemic_review_handler(project_id: int, payload: dict) -> dict:
    reviewed = []
    for claim in list_claims(project_id, limit=300):
        if claim["status"] == "superseded":
            continue
        result = verify_claim(project_id, int(claim["id"]))
        reviewed.append({
            "claim_id": result.claim_id,
            "status": result.status,
            "confidence": result.confidence,
            "reason": result.reason,
        })
    return {
        "reviewed": len(reviewed),
        "snapshot": epistemic_snapshot(project_id),
        "items": reviewed[:100],
        "note": "Ревизия переоценивает только по уже сохранённым свидетельствам; новых внешних фактов не выдумывает.",
    }


def agent_workspace_handler(project_id: int, payload: dict) -> dict:
    return run_agent_workspace_cycle(project_id, payload)


def register_background_handlers() -> None:
    register_task_handler("agent_workspace", agent_workspace_handler)
    register_task_handler("self_check", self_check_handler)
    register_task_handler("memory_consolidation", memory_consolidation_handler)
    register_task_handler("epistemic_review", epistemic_review_handler)
    register_task_handler("document_intelligence", document_intelligence_handler)
    register_task_handler("document_vision", document_vision_handler)
    register_task_handler("document_question", document_question_handler)
