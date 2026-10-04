from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import connect, create_project, init_db
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db
from miyori.epistemic import init_epistemic_db
from miyori.nexus_proactive import (
    NEXUS_PROACTIVE_SCHEMA_VERSION,
    build_nexus_proactive,
    init_proactive_db,
    set_proactive_disposition,
)
from miyori.tools import execute_tool


class NexusProactiveContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_document_questions_db()
        init_epistemic_db()
        init_proactive_db()
        self.project = create_project("NEXUS Proactive", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _waiting_signal(self, suffix: str = "1") -> dict:
        result = execute_tool(
            "workspace_create",
            self.project_id,
            {"path": f"proactive-{suffix}.txt", "content": "hello"},
            reason="Создать файл.",
            idempotency_key=f"proactive:test:{suffix}",
        )
        self.assertEqual(result["status"], "approval_required")
        page = build_nexus_proactive(self.project_id)
        return next(item for item in page["signals"] if item["category"] == "action")

    def test_waiting_action_becomes_non_executing_proactive_signal(self) -> None:
        signal = self._waiting_signal()
        page = build_nexus_proactive(self.project_id)

        self.assertEqual(page["schema_version"], NEXUS_PROACTIVE_SCHEMA_VERSION)
        self.assertIn(signal, page["signals"])
        self.assertEqual(signal["priority"], "normal")
        self.assertEqual(signal["action"]["target"], "actions")
        self.assertFalse(signal["policy"]["auto_execute_allowed"])
        self.assertFalse(signal["policy"]["write_tools_allowed"])
        self.assertFalse(signal["policy"]["chat_interruption_allowed"])
        self.assertFalse(signal["policy"]["creates_chat_message"])
        self.assertTrue(signal["policy"]["requires_explicit_user_action"])

    def test_dismiss_persists_and_does_not_mutate_underlying_action(self) -> None:
        signal = self._waiting_signal("dismiss")
        set_proactive_disposition(
            self.project_id,
            signal["id"],
            disposition="dismissed",
        )

        page = build_nexus_proactive(self.project_id)
        self.assertEqual(page["counts"]["dismissed"], 1)
        self.assertFalse(any(item["id"] == signal["id"] for item in page["signals"]))

        with connect() as conn:
            request = conn.execute(
                """
                SELECT status
                FROM permission_requests
                WHERE project_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (self.project_id,),
            ).fetchone()
        self.assertEqual(request["status"], "pending")

    def test_snooze_is_persistent_and_bounded(self) -> None:
        signal = self._waiting_signal("snooze")
        result = set_proactive_disposition(
            self.project_id,
            signal["id"],
            disposition="snoozed",
            snooze_minutes=60,
        )
        self.assertIsNotNone(result["snoozed_until"])

        init_proactive_db()
        page = build_nexus_proactive(self.project_id)
        self.assertEqual(page["counts"]["snoozed"], 1)
        self.assertFalse(any(item["id"] == signal["id"] for item in page["signals"]))

    def test_low_initiative_caps_visible_attention_to_one(self) -> None:
        self._waiting_signal("budget-a")
        self._waiting_signal("budget-b")
        with connect() as conn:
            conn.execute(
                """
                UPDATE ai_preferences
                SET initiative_level = 'low', updated_at = updated_at
                WHERE id = 1
                """
            )

        page = build_nexus_proactive(self.project_id)
        self.assertEqual(page["initiative_level"], "low")
        self.assertEqual(page["budget"]["effective_max_visible"], 1)
        self.assertEqual(len(page["signals"]), 1)
        self.assertGreaterEqual(page["counts"]["budget_suppressed"], 1)

    def test_dismissed_signal_does_not_hide_new_distinct_signal(self) -> None:
        first = self._waiting_signal("first")
        set_proactive_disposition(
            self.project_id,
            first["id"],
            disposition="dismissed",
        )
        second = self._waiting_signal("second")
        self.assertNotEqual(first["id"], second["id"])

        page = build_nexus_proactive(self.project_id)
        visible_ids = {item["id"] for item in page["signals"]}
        self.assertNotIn(first["id"], visible_ids)
        self.assertIn(second["id"], visible_ids)

    def test_server_policy_never_allows_chat_interruption_or_tool_execution(self) -> None:
        page = build_nexus_proactive(self.project_id)
        self.assertFalse(page["policy"]["chat_interruption_allowed"])
        self.assertFalse(page["policy"]["auto_execute_allowed"])
        self.assertFalse(page["policy"]["write_tools_allowed"])
        self.assertFalse(page["policy"]["creates_chat_messages"])
        self.assertTrue(page["policy"]["persistent_dismiss_snooze"])
        self.assertTrue(page["policy"]["derived_from_authoritative_state"])


if __name__ == "__main__":
    unittest.main()
