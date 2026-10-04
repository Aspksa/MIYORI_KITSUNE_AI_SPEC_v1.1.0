from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    create_agent_workflow,
    create_permission_request,
    create_project,
    create_tool_operation,
    create_workflow_step,
    decide_permission_request,
    init_db,
    link_tool_operation_permission,
    start_agent_run,
    update_agent_workflow,
    update_tool_operation,
    update_workflow_step,
)
from miyori.nexus_actions import build_nexus_action_center
from miyori.tools import execute_approved_request, execute_tool


class NexusActionsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("NEXUS Actions", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_standalone_write_action_exposes_preview_and_real_completion(self) -> None:
        result = execute_tool(
            "workspace_create",
            self.project_id,
            {"path": "notes/action.txt", "content": "hello"},
            reason="Создать рабочий файл.",
            idempotency_key="test:standalone:1",
        )
        self.assertEqual(result["status"], "approval_required")
        request_id = int(result["permission_request"]["id"])

        center = build_nexus_action_center(self.project_id)
        card = next(item for item in center["actions"] if item["permission_id"] == request_id)
        self.assertEqual(card["state"], "waiting_permission")
        self.assertTrue(card["preview"])
        self.assertEqual(card["controls"]["approve_permission"], request_id)
        self.assertEqual(center["counts"]["attention"], 1)

        decide_permission_request(self.project_id, request_id, True)
        execution = execute_approved_request(self.project_id, request_id)
        self.assertEqual(execution["status"], "executed")

        center = build_nexus_action_center(self.project_id)
        card = next(item for item in center["actions"] if item["permission_id"] == request_id)
        self.assertEqual(card["state"], "completed")
        self.assertIsNotNone(card["result"])
        self.assertIsNone(card["controls"]["approve_permission"])

    def test_workflow_embeds_permission_without_duplicate_action_card(self) -> None:
        run_id = start_agent_run(self.project_id, None, "Создать файл", 3)
        workflow = create_agent_workflow(
            project_id=self.project_id,
            conversation_id=None,
            agent_run_id=run_id,
            request_key="test:workflow:1",
            goal="Создать файл",
            route={},
            conversation_context=[],
            max_steps=3,
        )
        workflow_id = int(workflow["id"])
        step = create_workflow_step(
            workflow_id,
            1,
            "tool",
            "Нужно создать файл.",
            tool_name="workspace_create",
            arguments={"path": "workflow.txt", "content": "hello"},
            status="waiting_permission",
            idempotency_key="workflow:test:1",
        )
        operation = create_tool_operation(
            self.project_id,
            "workspace_create",
            "workflow:test:1",
            {"path": "workflow.txt", "content": "hello"},
            workflow_id=workflow_id,
            workflow_step_id=int(step["id"]),
            preflight={"path": "workflow.txt", "exists": False},
        )
        request = create_permission_request(
            self.project_id,
            "workspace_create",
            {"path": "workflow.txt", "content": "hello"},
            "Подтвердить создание.",
            workflow_id=workflow_id,
            workflow_step_id=int(step["id"]),
            tool_operation_id=int(operation["id"]),
            idempotency_key="workflow:test:1",
            preview={
                "title": "Создание файла",
                "summary": "Будет создан workflow.txt",
                "changes": [{"field": "path", "value": "workflow.txt"}],
            },
        )
        link_tool_operation_permission(int(operation["id"]), int(request["id"]))
        update_workflow_step(
            int(step["id"]),
            status="waiting_permission",
            permission_request_id=int(request["id"]),
        )
        update_agent_workflow(
            workflow_id,
            status="waiting_permission",
            current_step=1,
            pending_permission_id=int(request["id"]),
        )

        center = build_nexus_action_center(self.project_id)
        related = [
            item
            for item in center["actions"]
            if item.get("workflow_id") == workflow_id
            or item.get("permission_id") == int(request["id"])
        ]
        self.assertEqual(len(related), 1)
        card = related[0]
        self.assertEqual(card["kind"], "workflow")
        self.assertEqual(card["state"], "waiting_permission")
        self.assertEqual(card["permission_id"], int(request["id"]))
        self.assertEqual(card["preview"]["summary"], "Будет создан workflow.txt")
        self.assertEqual(center["counts"]["waiting_permission"], 1)

    def test_verifying_is_a_real_persisted_action_state(self) -> None:
        operation = create_tool_operation(
            self.project_id,
            "workspace_create",
            "test:verifying:1",
            {"path": "verify.txt", "content": "hello"},
            preflight={"path": "verify.txt", "exists": False},
        )
        update_tool_operation(int(operation["id"]), status="verifying", mark_started=True)
        center = build_nexus_action_center(self.project_id)
        card = next(
            item for item in center["actions"]
            if item.get("operation_id") == int(operation["id"])
        )
        self.assertEqual(card["state"], "verifying")
        self.assertEqual(card["state_label"], "Проверяется")
        self.assertEqual(center["counts"]["verifying"], 1)


if __name__ == "__main__":
    unittest.main()
