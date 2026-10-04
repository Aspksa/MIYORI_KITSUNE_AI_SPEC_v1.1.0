from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_memory_fact,
    create_project,
    create_tool_operation,
    init_db,
    update_tool_operation,
)
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db
from miyori.epistemic import init_epistemic_db
from miyori.nexus_presence import (
    NEXUS_PRESENCE_SCHEMA_VERSION,
    build_nexus_presence,
)
from miyori.tools import execute_tool


class NexusPresenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        self.old_api_key = settings.cloudru_api_key
        self.old_model_id = settings.cloudru_model_id
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        object.__setattr__(settings, "cloudru_api_key", "presence-test-key")
        object.__setattr__(settings, "cloudru_model_id", "model/presence-test")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_document_questions_db()
        init_epistemic_db()
        self.project = create_project("NEXUS Presence", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        object.__setattr__(settings, "cloudru_api_key", self.old_api_key)
        object.__setattr__(settings, "cloudru_model_id", self.old_model_id)
        self.tmp.cleanup()

    def test_idle_project_is_ready_without_fake_activity(self) -> None:
        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["schema_version"], NEXUS_PRESENCE_SCHEMA_VERSION)
        self.assertEqual(presence["mode"], "ready")
        self.assertEqual(presence["attention"], "none")
        self.assertEqual(presence["activity"]["active_actions"], 0)
        self.assertFalse(presence["source_contract"]["random_liveness_allowed"])
        self.assertFalse(presence["source_contract"]["decorative_activity_allowed"])
        self.assertFalse(presence["source_contract"]["chat_interruption_allowed"])

    def test_permission_waiting_has_priority_over_ready_state(self) -> None:
        result = execute_tool(
            "workspace_create",
            self.project_id,
            {"path": "presence.txt", "content": "hello"},
            reason="Создать файл.",
            idempotency_key="presence:test:permission",
        )
        self.assertEqual(result["status"], "approval_required")

        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["mode"], "waiting")
        self.assertEqual(presence["attention"], "normal")
        self.assertEqual(presence["activity"]["waiting_permissions"], 1)
        self.assertEqual(presence["reasons"][0]["kind"], "permission")

    def test_verifying_is_visible_as_its_real_presence_phase(self) -> None:
        operation = create_tool_operation(
            self.project_id,
            "workspace_create",
            "presence:test:verifying",
            {"path": "verify.txt", "content": "hello"},
            preflight={"path": "verify.txt", "exists": False},
        )
        update_tool_operation(
            int(operation["id"]),
            status="verifying",
            mark_started=True,
        )

        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["mode"], "verifying")
        self.assertEqual(presence["activity"]["verifying_actions"], 1)

    def test_recovery_has_highest_operational_priority(self) -> None:
        operation = create_tool_operation(
            self.project_id,
            "workspace_create",
            "presence:test:recovery",
            {"path": "recover.txt", "content": "hello"},
            preflight={"path": "recover.txt", "exists": False},
        )
        update_tool_operation(
            int(operation["id"]),
            status="recovery_required",
            error={"message": "Interrupted"},
        )

        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["mode"], "recovery")
        self.assertEqual(presence["attention"], "high")
        self.assertEqual(presence["activity"]["recovering_actions"], 1)

    def test_verifying_is_exposed_as_distinct_real_state(self) -> None:
        operation = create_tool_operation(
            self.project_id,
            "workspace_create",
            "presence:test:verifying",
            {"path": "verify.txt", "content": "hello"},
            preflight={"path": "verify.txt", "exists": False},
        )
        update_tool_operation(
            int(operation["id"]),
            status="verifying",
            mark_started=True,
        )

        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["mode"], "verifying")
        self.assertEqual(presence["headline"], "Проверяю")
        self.assertEqual(presence["activity"]["active_actions"], 1)

    def test_knowledge_attention_does_not_hijack_primary_presence(self) -> None:
        add_memory_fact(
            self.project_id,
            "Budget needs confirmation.",
            status="disputed",
            memory_scope="project",
            memory_kind="constraint",
        )
        presence = build_nexus_presence(self.project_id)
        self.assertEqual(presence["mode"], "ready")
        self.assertGreater(presence["activity"]["knowledge_attention"], 0)
        self.assertFalse(
            presence["source_contract"]["knowledge_attention_changes_primary_presence"]
        )

    def test_presence_exposes_only_real_sources(self) -> None:
        presence = build_nexus_presence(self.project_id)
        self.assertEqual(
            set(presence["source_contract"]["sources"]),
            {"nexus_snapshot", "nexus_actions", "nexus_events"},
        )
        self.assertNotIn("mood", presence)
        self.assertNotIn("random_animation", presence)


if __name__ == "__main__":
    unittest.main()
