from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_memory_fact,
    connect,
    create_project,
    get_ai_preferences,
    init_db,
    list_audit_events,
    update_ai_preferences,
)
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db
from miyori.epistemic import init_epistemic_db
from miyori.proactive import (
    NEXUS_PROACTIVE_SCHEMA_VERSION,
    apply_proactive_decision,
    build_nexus_proactive,
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
        self.project = create_project("NEXUS Proactive", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _set_initiative(self, level: str, suggest: bool = True) -> None:
        current = get_ai_preferences()
        update_ai_preferences(
            communication_style=current.get("communication_style", "balanced"),
            detail_level=current.get("detail_level", "normal"),
            initiative_level=level,
            ask_before_assuming=bool(current.get("ask_before_assuming", 0)),
            suggest_next_steps=suggest,
            use_rag=bool(current.get("use_rag", 1)),
            use_verified_memory=bool(current.get("use_verified_memory", 1)),
            show_uncertainty=bool(current.get("show_uncertainty", 1)),
            priority_mode=current.get("priority_mode", "accuracy"),
            operating_mode=current.get("operating_mode", "personal"),
        )

    def _add_knowledge_attention(self, statement: str) -> None:
        add_memory_fact(
            self.project_id,
            statement,
            status="disputed",
            memory_scope="project",
            memory_kind="constraint",
        )

    def test_operational_blocker_is_presence_owned_and_never_auto_executes(self) -> None:
        result = execute_tool(
            "workspace_create",
            self.project_id,
            {"path": "proactive.txt", "content": "hello"},
            reason="Создать файл.",
            idempotency_key="proactive:permission:1",
        )
        self.assertEqual(result["status"], "approval_required")

        page = build_nexus_proactive(self.project_id)
        self.assertEqual(page["schema_version"], NEXUS_PROACTIVE_SCHEMA_VERSION)
        blocker = next(
            item for item in page["signals"] if item["kind"] == "operational"
        )

        self.assertEqual(blocker["channel_owner"], "presence")
        self.assertIn(blocker["id"], page["display"]["presence_owned_ids"])
        self.assertNotIn(blocker["id"], page["display"]["chat_shelf_ids"])
        self.assertFalse(page["policy"]["auto_execute_allowed"])
        self.assertFalse(page["policy"]["write_action_allowed"])
        self.assertFalse(page["policy"]["chat_message_injection_allowed"])
        self.assertTrue(blocker["safety"]["requires_existing_permission_flow"])

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

    def test_medium_initiative_allows_one_integrity_signal_in_quiet_shelf(self) -> None:
        self._set_initiative("medium", suggest=True)
        self._add_knowledge_attention("Budget is disputed.")

        page = build_nexus_proactive(self.project_id)
        signal = next(
            item
            for item in page["signals"]
            if item["kind"] == "knowledge_integrity"
        )

        self.assertEqual(signal["channel_owner"], "attention_shelf")
        self.assertEqual(page["budget"]["max_chat_shelf"], 1)
        self.assertEqual(page["display"]["chat_shelf_ids"], [signal["id"]])

    def test_low_initiative_keeps_advisory_signal_out_of_chat_shelf(self) -> None:
        self._set_initiative("low", suggest=True)
        self._add_knowledge_attention("Delivery date is disputed.")

        page = build_nexus_proactive(self.project_id)
        self.assertTrue(
            any(item["kind"] == "knowledge_integrity" for item in page["signals"])
        )
        self.assertEqual(page["budget"]["max_chat_shelf"], 0)
        self.assertEqual(page["display"]["chat_shelf_ids"], [])

    def test_suggest_next_steps_off_disables_advisory_shelf(self) -> None:
        self._set_initiative("high", suggest=False)
        self._add_knowledge_attention("Contract amount is disputed.")

        page = build_nexus_proactive(self.project_id)
        self.assertEqual(page["budget"]["max_chat_shelf"], 0)
        self.assertEqual(page["display"]["chat_shelf_ids"], [])

    def test_dismiss_is_fingerprint_scoped_and_does_not_hide_changed_reality(self) -> None:
        self._add_knowledge_attention("Budget limit is disputed.")
        before = build_nexus_proactive(self.project_id)
        signal = next(
            item
            for item in before["signals"]
            if item["kind"] == "knowledge_integrity"
        )

        result = apply_proactive_decision(
            self.project_id,
            signal_key=signal["signal_key"],
            fingerprint=signal["fingerprint"],
            decision="dismissed",
        )
        self.assertTrue(result["ok"])
        after = result["proactive"]
        self.assertNotIn(signal["id"], [item["id"] for item in after["signals"]])
        self.assertTrue(
            any(
                item["signal_key"] == signal["signal_key"]
                and item["reason"] == "dismissed"
                for item in after["suppressed"]
            )
        )

        self._add_knowledge_attention("Another disputed constraint.")
        changed = build_nexus_proactive(self.project_id)
        next_signal = next(
            item
            for item in changed["signals"]
            if item["kind"] == "knowledge_integrity"
        )
        self.assertNotEqual(next_signal["fingerprint"], signal["fingerprint"])

        audit = list_audit_events(self.project_id, limit=20)
        self.assertTrue(
            any(item["event_type"] == "proactive.dismissed" for item in audit)
        )

    def test_snooze_persists_and_reports_next_wakeup(self) -> None:
        self._add_knowledge_attention("Evidence needs review.")
        before = build_nexus_proactive(self.project_id)
        signal = next(
            item
            for item in before["signals"]
            if item["kind"] == "knowledge_integrity"
        )

        result = apply_proactive_decision(
            self.project_id,
            signal_key=signal["signal_key"],
            fingerprint=signal["fingerprint"],
            decision="snoozed",
            snooze_minutes=60,
        )
        self.assertIsNotNone(result["snoozed_until"])

        # Re-running init_db represents a process restart; the decision must survive.
        init_db()
        after = build_nexus_proactive(self.project_id)
        self.assertNotIn(signal["id"], [item["id"] for item in after["signals"]])
        self.assertIsNotNone(after["next_wakeup_at"])
        self.assertTrue(
            any(
                item["signal_key"] == signal["signal_key"]
                and item["reason"] == "snoozed"
                for item in after["suppressed"]
            )
        )

    def test_policy_forbids_chat_injection_interruptions_and_os_notifications(self) -> None:
        page = build_nexus_proactive(self.project_id)
        policy = page["policy"]
        self.assertFalse(policy["auto_execute_allowed"])
        self.assertFalse(policy["write_action_allowed"])
        self.assertFalse(policy["chat_message_injection_allowed"])
        self.assertFalse(policy["interrupt_user_allowed"])
        self.assertFalse(policy["os_notification_allowed"])
        self.assertTrue(policy["operational_blockers_owned_by_presence"])
        self.assertTrue(policy["decisions_change_signal_visibility_only"])


if __name__ == "__main__":
    unittest.main()
