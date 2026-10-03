from __future__ import annotations

from .db import list_memory_facts
from .epistemic import epistemic_snapshot, list_claims, verify_claim
from .development import run_project_self_check
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


def register_background_handlers() -> None:
    register_task_handler("self_check", self_check_handler)
    register_task_handler("memory_consolidation", memory_consolidation_handler)
    register_task_handler("epistemic_review", epistemic_review_handler)
