from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db
from miyori.epistemic import init_epistemic_db
from miyori.nexus_surfaces import (
    NEXUS_SURFACE_COMPONENTS,
    NEXUS_SURFACE_KINDS,
    NEXUS_SURFACE_SCHEMA_VERSION,
    build_nexus_surfaces,
)
from miyori.tools import execute_tool


class NexusSurfaceContractTests(unittest.TestCase):
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
        self.project = create_project("NEXUS Surfaces", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_registry_is_closed_and_disallows_model_markup(self) -> None:
        payload = build_nexus_surfaces(self.project_id, context="chat")
        self.assertEqual(payload["schema_version"], NEXUS_SURFACE_SCHEMA_VERSION)
        self.assertEqual(
            set(payload["registry"]["allowed_kinds"]),
            NEXUS_SURFACE_KINDS,
        )
        self.assertEqual(
            set(payload["registry"]["allowed_components"]),
            NEXUS_SURFACE_COMPONENTS,
        )
        self.assertFalse(payload["registry"]["model_html_allowed"])
        self.assertFalse(payload["registry"]["script_allowed"])
        self.assertTrue(payload["registry"]["unknown_components_rejected"])

    def test_waiting_permission_becomes_one_safe_action_surface(self) -> None:
        result = execute_tool(
            "workspace_create",
            self.project_id,
            {"path": "surface.txt", "content": "hello"},
            reason="Создать файл.",
            idempotency_key="surface:test:1",
        )
        self.assertEqual(result["status"], "approval_required")

        payload = build_nexus_surfaces(self.project_id, context="chat", limit=3)
        surfaces = payload["surfaces"]
        action = next(item for item in surfaces if item["kind"] == "action")
        self.assertEqual(action["component"], "action_card")
        self.assertEqual(action["data"]["state"], "waiting_permission")
        self.assertEqual(action["actions"][0]["type"], "navigate")
        self.assertEqual(action["actions"][0]["target"], "actions")
        self.assertFalse(action["policy"]["model_html_allowed"])
        self.assertFalse(action["policy"]["script_allowed"])

    def test_unknown_context_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_nexus_surfaces(self.project_id, context="arbitrary-html")

    def test_limit_is_enforced(self) -> None:
        execute_tool(
            "workspace_create",
            self.project_id,
            {"path": "surface-limit.txt", "content": "hello"},
            reason="Создать файл.",
            idempotency_key="surface:test:2",
        )
        payload = build_nexus_surfaces(self.project_id, context="auto", limit=1)
        self.assertLessEqual(len(payload["surfaces"]), 1)


if __name__ == "__main__":
    unittest.main()
