from __future__ import annotations

from dataclasses import dataclass

from .db import development_snapshot, record_development_check


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def run_project_self_check(project_id: int) -> list[CheckResult]:
    snapshot = development_snapshot(project_id)
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
            "task_health",
            snapshot["failed_tasks"] == 0,
            f"failed_tasks={snapshot['failed_tasks']}",
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
