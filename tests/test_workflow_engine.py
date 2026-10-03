from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app as app_module
from miyori.config import settings
from miyori.db import (
    conversation_messages,
    create_project,
    get_agent_workflow,
    get_permission_request,
    init_db,
    list_audit_events,
    list_document_folders,
)
from miyori.documents import project_document_dir


class _FakeRag:
    def to_dict(self) -> dict:
        return {
            "query": "",
            "items": [],
            "retrieval_mode": "disabled",
            "total_chars": 0,
            "candidates_seen": 0,
        }


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("Workflow Test")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _patch_app_context(self):
        return (
            patch.object(app_module, "rag_retrieve", return_value=_FakeRag()),
            patch.object(app_module, "capture_user_claims", return_value=[]),
            patch.object(app_module, "trusted_claim_context", return_value=[]),
            patch.object(
                app_module,
                "epistemic_snapshot",
                return_value={
                    "claims": {},
                    "sources": 0,
                    "open_contradictions": 0,
                    "assessment": {},
                },
            ),
        )

    def test_permission_continues_same_workflow_and_is_idempotent(self) -> None:
        planner = AsyncMock(side_effect=[
            {
                "action": "tool",
                "tool_name": "drive_folder_create",
                "arguments": {"name": "Договоры 2027", "parent_id": None},
                "reason": "Пользователь явно просит создать папку.",
            },
            {
                "action": "finish",
                "tool_name": None,
                "arguments": {},
                "reason": "Папка создана и результат проверен.",
            },
        ])
        chat = AsyncMock(side_effect=[
            "Для создания папки требуется подтверждение.",
            "Папка «Договоры 2027» создана.",
        ])

        patches = self._patch_app_context()
        with patches[0], patches[1], patches[2], patches[3],              patch("miyori.agent.plan_next_action", planner),              patch.object(app_module, "chat", chat):
            initial = asyncio.run(
                app_module.send_message(
                    app_module.ChatRequest(
                        message='Создай папку «Договоры 2027»',
                        project_id=self.project_id,
                        request_id="chat-request-0001",
                    )
                )
            )

            self.assertEqual(initial["workflow"]["status"], "waiting_permission")
            self.assertEqual(len(initial["agent"]["pending_permissions"]), 1)
            permission_id = int(initial["agent"]["pending_permissions"][0]["id"])
            workflow_id = int(initial["workflow"]["id"])

            target = (
                project_document_dir(self.project_id)
                / "Договоры 2027"
            )
            self.assertFalse(target.exists())

            approved = asyncio.run(
                app_module.permission_decision(
                    self.project_id,
                    permission_id,
                    app_module.PermissionDecisionRequest(approved=True),
                )
            )
            self.assertEqual(approved["request"]["status"], "executed")
            self.assertEqual(
                approved["workflow"]["workflow_status"],
                "completed",
            )
            self.assertEqual(
                approved["continuation"]["answer"],
                "Папка «Договоры 2027» создана.",
            )
            self.assertTrue(target.is_dir())
            self.assertEqual(
                sum(
                    1 for item in list_document_folders(self.project_id)
                    if item["name"] == "Договоры 2027"
                ),
                1,
            )

            messages_before = conversation_messages(
                initial["conversation_id"],
                self.project_id,
            )
            chat_calls_before = chat.await_count

            repeated_permission = asyncio.run(
                app_module.permission_decision(
                    self.project_id,
                    permission_id,
                    app_module.PermissionDecisionRequest(approved=True),
                )
            )
            self.assertEqual(repeated_permission["request"]["status"], "executed")
            self.assertEqual(chat.await_count, chat_calls_before)
            self.assertEqual(
                len(
                    conversation_messages(
                        initial["conversation_id"],
                        self.project_id,
                    )
                ),
                len(messages_before),
            )

            replay = asyncio.run(
                app_module.send_message(
                    app_module.ChatRequest(
                        message='Создай папку «Договоры 2027»',
                        project_id=self.project_id,
                        conversation_id=initial["conversation_id"],
                        request_id="chat-request-0001",
                    )
                )
            )
            self.assertEqual(replay["workflow"]["status"], "completed")
            self.assertEqual(chat.await_count, chat_calls_before)

            workflow = get_agent_workflow(workflow_id, self.project_id)
            self.assertEqual(workflow["status"], "completed")
            audit_types = {
                item["event_type"]
                for item in list_audit_events(self.project_id, workflow_id=workflow_id)
            }
            self.assertIn("workflow.started", audit_types)
            self.assertIn("permission.approved", audit_types)
            self.assertIn("tool.executed", audit_types)
            self.assertIn("workflow.completed", audit_types)

    def test_denied_write_is_not_executed_and_workflow_can_finish(self) -> None:
        planner = AsyncMock(side_effect=[
            {
                "action": "tool",
                "tool_name": "drive_folder_create",
                "arguments": {"name": "Не создавать", "parent_id": None},
                "reason": "Пользователь просит создать папку.",
            },
            {
                "action": "finish",
                "tool_name": None,
                "arguments": {},
                "reason": "Пользователь отклонил изменение; завершаю без изменений.",
            },
        ])
        chat = AsyncMock(side_effect=[
            "Нужно подтверждение.",
            "Действие отклонено. Изменений не внесено.",
        ])
        patches = self._patch_app_context()
        with patches[0], patches[1], patches[2], patches[3],              patch("miyori.agent.plan_next_action", planner),              patch.object(app_module, "chat", chat):
            initial = asyncio.run(
                app_module.send_message(
                    app_module.ChatRequest(
                        message='Создай папку «Не создавать»',
                        project_id=self.project_id,
                        request_id="chat-request-0002",
                    )
                )
            )
            permission_id = int(initial["agent"]["pending_permissions"][0]["id"])
            denied = asyncio.run(
                app_module.permission_decision(
                    self.project_id,
                    permission_id,
                    app_module.PermissionDecisionRequest(approved=False),
                )
            )

            self.assertEqual(
                get_permission_request(self.project_id, permission_id)["status"],
                "denied",
            )
            self.assertEqual(
                denied["workflow"]["workflow_status"],
                "completed",
            )
            self.assertFalse(
                (project_document_dir(self.project_id) / "Не создавать").exists()
            )


if __name__ == "__main__":
    unittest.main()
