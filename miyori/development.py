from __future__ import annotations

from dataclasses import dataclass

from .db import development_snapshot, record_development_check
from .rag import rag_status


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def run_project_self_check(project_id: int) -> list[CheckResult]:
    snapshot = development_snapshot(project_id)
    rag = rag_status()
    rag_ok = (not rag["fts5"]) or rag["indexed_chunks"] == snapshot["document_chunks"]
    checks = [
        CheckResult(
            "memory_integrity",
            snapshot["verified_facts"] >= 0,
            f"verified_facts={snapshot['verified_facts']}",
        ),
        CheckResult(
            "document_index",
            snapshot["documents"] >= 0 and snapshot["document_chunks"] >= 0,
            f"documents={snapshot['documents']}; chunks={snapshot['document_chunks']}",
        ),
        CheckResult(
            "rag_index",
            rag_ok,
            (
                f"mode={'fts5' if rag['fts5'] else 'lexical_fallback'}; "
                f"indexed_chunks={rag['indexed_chunks']}; document_chunks={snapshot['document_chunks']}"
            ),
        ),
        CheckResult(
            "task_health",
            snapshot["failed_tasks"] == 0,
            f"failed_tasks={snapshot['failed_tasks']}",
        ),
        CheckResult(
            "workflow_recovery",
            snapshot["recovering_workflows"] == 0
            and snapshot["recovery_operations"] == 0,
            (
                f"recovering_workflows={snapshot['recovering_workflows']}; "
                f"recovery_operations={snapshot['recovery_operations']}; "
                f"waiting_workflows={snapshot['waiting_workflows']}; "
                f"pending_permissions={snapshot['pending_permissions']}"
            ),
        ),
    ]

    for check in checks:
        record_development_check(
            project_id=project_id,
            name=check.name,
            passed=check.passed,
            details=check.details,
        )

    return checks
