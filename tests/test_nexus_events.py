from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    create_agent_workflow,
    create_project,
    create_task,
    init_db,
    record_audit_event,
    record_task_event,
    record_workflow_event,
)
from miyori.nexus_events import (
    NEXUS_EVENT_SCHEMA_VERSION,
    list_nexus_events,
)


class NexusEventFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path

        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(
            settings,
            "database_path",
            root / "data" / "miyori.sqlite3",
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("NEXUS Events", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _seed_all_sources(self) -> None:
        record_audit_event(
            self.project_id,
            "user",
            "test.audit",
            "Пользовательское событие.",
            entity_type="test",
            entity_id="audit",
            details={"value": 1},
        )
        workflow = create_agent_workflow(
            project_id=self.project_id,
            conversation_id=None,
            agent_run_id=None,
            request_key="nexus-event-test",
            goal="Проверить event fabric",
            route={},
            conversation_context=[],
            max_steps=5,
        )
        record_workflow_event(
            int(workflow["id"]),
            "workflow.test",
            {"value": 2},
        )
        task = create_task(
            self.project_id,
            "self_check",
            {},
        )
        record_task_event(
            int(task["id"]),
            "progress",
            '{"message":"Задача выполняется","value":3}',
        )

    def test_unifies_existing_event_sources_without_mutating_them(self) -> None:
        self._seed_all_sources()
        page = list_nexus_events(self.project_id, limit=20)

        self.assertEqual(
            page["schema_version"],
            NEXUS_EVENT_SCHEMA_VERSION,
        )
        self.assertTrue(page["resync"]["required_after_events"])
        self.assertTrue(page["next_cursor"])

        sources = {item["source"] for item in page["events"]}
        self.assertEqual(sources, {"audit", "workflow", "task"})
        self.assertTrue(
            all(item["requires_resync"] for item in page["events"])
        )
        self.assertTrue(
            all(
                item["schema_version"] == NEXUS_EVENT_SCHEMA_VERSION
                for item in page["events"]
            )
        )

    def test_cursor_is_incremental_and_does_not_repeat_events(self) -> None:
        self._seed_all_sources()
        first = list_nexus_events(self.project_id, limit=2)
        self.assertEqual(len(first["events"]), 2)

        second = list_nexus_events(
            self.project_id,
            after=first["next_cursor"],
            limit=20,
        )
        first_ids = {item["id"] for item in first["events"]}
        second_ids = {item["id"] for item in second["events"]}
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(len(first_ids | second_ids), 3)

        empty = list_nexus_events(
            self.project_id,
            after=second["next_cursor"],
            limit=20,
        )
        self.assertEqual(empty["events"], [])

    def test_project_isolation_applies_to_event_stream(self) -> None:
        self._seed_all_sources()
        other = create_project("Other NEXUS Project", kind="work")
        record_audit_event(
            int(other["id"]),
            "system",
            "other.event",
            "Чужое событие.",
        )

        page = list_nexus_events(self.project_id, limit=50)
        self.assertTrue(page["events"])
        self.assertTrue(
            all(
                int(item["project_id"]) == self.project_id
                for item in page["events"]
            )
        )
        self.assertFalse(
            any(item["event_type"] == "other.event" for item in page["events"])
        )

    def test_invalid_cursor_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            list_nexus_events(self.project_id, after="not-a-valid-cursor")


if __name__ == "__main__":
    unittest.main()
