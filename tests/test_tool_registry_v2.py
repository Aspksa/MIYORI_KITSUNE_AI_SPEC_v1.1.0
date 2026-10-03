from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    create_project,
    decide_permission_request,
    get_permission_request,
    get_tool_operation,
    init_db,
    list_permission_requests,
    mark_interrupted_runtime_for_recovery,
    update_tool_operation,
)
from miyori.hands import create_workspace_file, resolve_workspace_path
from miyori.tools import (
    drive_folder_create,
    execute_approved_request,
    execute_tool,
    list_tools,
    reconcile_tool_operation,
)


class ToolRegistryV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("Tool Registry v2")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_registry_exposes_future_safe_metadata(self) -> None:
        tools = {item["name"]: item for item in list_tools()}
        move = tools["drive_document_move"]
        for key in (
            "version", "category", "risk_level", "destructive",
            "idempotent", "timeout_seconds", "rollback_capability",
            "recovery_strategy", "parameters",
        ):
            self.assertIn(key, move)

    def test_schema_validation_happens_before_permission(self) -> None:
        with self.assertRaises(ValueError):
            execute_tool(
                "project_document_read",
                self.project_id,
                {"document_id": 1, "limit": 999},
            )
        with self.assertRaises(ValueError):
            execute_tool(
                "drive_folder_create",
                self.project_id,
                {"name": "x" * 121, "parent_id": None},
            )
        self.assertEqual(list_permission_requests(self.project_id), [])

    def test_idempotency_reuses_permission_and_rejects_argument_conflict(self) -> None:
        first = execute_tool(
            "drive_folder_create",
            self.project_id,
            {"name": "Однократно", "parent_id": None},
            idempotency_key="idem-folder-0001",
        )
        second = execute_tool(
            "drive_folder_create",
            self.project_id,
            {"name": "Однократно", "parent_id": None},
            idempotency_key="idem-folder-0001",
        )
        self.assertEqual(
            first["permission_request"]["id"],
            second["permission_request"]["id"],
        )
        self.assertEqual(len(list_permission_requests(self.project_id)), 1)

        with self.assertRaises(ValueError):
            execute_tool(
                "drive_folder_create",
                self.project_id,
                {"name": "Другое имя", "parent_id": None},
                idempotency_key="idem-folder-0001",
            )

    def test_crash_after_side_effect_recovers_as_completed_without_repeating(self) -> None:
        created = execute_tool(
            "drive_folder_create",
            self.project_id,
            {"name": "Recovery", "parent_id": None},
            idempotency_key="recovery-folder-0001",
        )
        permission_id = int(created["permission_request"]["id"])
        operation_id = int(created["operation_id"])
        decide_permission_request(self.project_id, permission_id, True)

        # Simulate: handler finished, process died before operation/result commit.
        drive_folder_create(self.project_id, "Recovery", None)
        update_tool_operation(
            operation_id,
            status="running",
            increment_attempt=True,
            mark_started=True,
        )
        marked = mark_interrupted_runtime_for_recovery()
        self.assertGreaterEqual(marked["operations"], 1)

        recovered = reconcile_tool_operation(operation_id, allow_retry=True)
        self.assertEqual(recovered["state"], "recovered_as_completed")
        self.assertEqual(get_tool_operation(operation_id)["status"], "executed")
        self.assertEqual(
            get_permission_request(self.project_id, permission_id)["status"],
            "executed",
        )

    def test_stale_approval_is_blocked_before_normal_write(self) -> None:
        create_workspace_file(self.project_id, "stale.txt", "before")
        prepared = execute_tool(
            "workspace_modify",
            self.project_id,
            {"path": "stale.txt", "content": "desired"},
            idempotency_key="stale-approval-0001",
        )
        permission_id = int(prepared["permission_request"]["id"])
        decide_permission_request(self.project_id, permission_id, True)

        resolve_workspace_path(self.project_id, "stale.txt").write_text(
            "changed after approval",
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            execute_approved_request(self.project_id, permission_id)

        self.assertEqual(
            resolve_workspace_path(self.project_id, "stale.txt").read_text(encoding="utf-8"),
            "changed after approval",
        )
        self.assertEqual(
            get_permission_request(self.project_id, permission_id)["status"],
            "failed",
        )

    def test_external_change_blocks_automatic_retry(self) -> None:
        create_workspace_file(self.project_id, "safe.txt", "before")
        prepared = execute_tool(
            "workspace_modify",
            self.project_id,
            {"path": "safe.txt", "content": "desired"},
            idempotency_key="modify-conflict-0001",
        )
        operation_id = int(prepared["operation_id"])
        permission_id = int(prepared["permission_request"]["id"])
        decide_permission_request(self.project_id, permission_id, True)

        # External/user change after approval invalidates the preflight snapshot.
        resolve_workspace_path(self.project_id, "safe.txt").write_text(
            "external change",
            encoding="utf-8",
        )
        update_tool_operation(
            operation_id,
            status="recovery_required",
            error={"message": "simulated crash"},
        )

        result = reconcile_tool_operation(operation_id, allow_retry=True)
        self.assertEqual(result["state"], "recovery_required")
        self.assertEqual(
            resolve_workspace_path(self.project_id, "safe.txt").read_text(encoding="utf-8"),
            "external change",
        )


if __name__ == "__main__":
    unittest.main()
