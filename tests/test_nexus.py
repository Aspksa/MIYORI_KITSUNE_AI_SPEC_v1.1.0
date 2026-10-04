from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.document_intelligence import init_document_intelligence_db
from miyori.epistemic import init_epistemic_db
from miyori.nexus import (
    NEXUS_OPERATIONAL_STATES,
    NEXUS_SCHEMA_VERSION,
    build_nexus_snapshot,
)


class NexusContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        self.old_key = settings.cloudru_api_key
        self.old_model = settings.cloudru_model_id

        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(
            settings,
            "database_path",
            root / "data" / "miyori.sqlite3",
        )
        object.__setattr__(settings, "cloudru_api_key", "")
        object.__setattr__(settings, "cloudru_model_id", "")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_epistemic_db()

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        object.__setattr__(settings, "cloudru_api_key", self.old_key)
        object.__setattr__(settings, "cloudru_model_id", self.old_model)
        self.tmp.cleanup()

    def test_snapshot_keeps_legacy_fields_and_adds_versioned_contract(self) -> None:
        project = create_project("NEXUS Test", kind="work")
        snapshot = build_nexus_snapshot(int(project["id"]))

        self.assertEqual(snapshot["schema_version"], NEXUS_SCHEMA_VERSION)
        self.assertIn("counts", snapshot)
        self.assertIn("suggestions", snapshot)
        self.assertIn("epistemic", snapshot)
        self.assertIn("documents", snapshot["counts"])
        self.assertIn("active_workflows", snapshot["counts"])
        self.assertIn("recovering_workflows", snapshot["counts"])
        self.assertIn("knowledge_attention", snapshot["counts"])
        self.assertEqual(snapshot["counts"]["active_workflows"], 0)
        self.assertTrue(snapshot["suggestions"])

        self.assertIn(snapshot["overall_state"], NEXUS_OPERATIONAL_STATES)
        self.assertFalse(snapshot["ui_contract"]["model_html_allowed"])
        self.assertEqual(snapshot["ui_contract"]["state_source"], "server_snapshot")

        modules = {item["id"]: item for item in snapshot["modules"]}
        for module_id in (
            "ai",
            "memory",
            "documents",
            "agents",
            "background",
            "epistemic",
            "home",
            "voice",
            "desktop",
            "generative_ui",
        ):
            self.assertIn(module_id, modules)
            self.assertIn(modules[module_id]["state"], NEXUS_OPERATIONAL_STATES)
            self.assertIn("last_result", modules[module_id])
            self.assertIn("limitation", modules[module_id])

        self.assertEqual(modules["ai"]["state"], "not_connected")
        self.assertEqual(modules["home"]["state"], "disabled")
        self.assertEqual(modules["voice"]["state"], "not_connected")
        self.assertEqual(modules["desktop"]["state"], "disabled")
        self.assertEqual(modules["generative_ui"]["state"], "disabled")

    def test_configured_provider_is_ready_without_faking_live_health(self) -> None:
        object.__setattr__(settings, "cloudru_api_key", "configured-key")
        object.__setattr__(settings, "cloudru_model_id", "model/test")
        project = create_project("NEXUS Provider", kind="work")
        snapshot = build_nexus_snapshot(int(project["id"]))
        modules = {item["id"]: item for item in snapshot["modules"]}
        self.assertEqual(modules["ai"]["state"], "ready")
        self.assertIn("health-check", modules["ai"]["limitation"])
        self.assertEqual(snapshot["overall_state"], "ready")

    def test_home_project_reports_home_capability_ready(self) -> None:
        project = create_project("NEXUS Home", kind="home")
        snapshot = build_nexus_snapshot(int(project["id"]))
        modules = {item["id"]: item for item in snapshot["modules"]}
        self.assertEqual(modules["home"]["state"], "ready")

    def test_snapshot_does_not_expose_provider_secret(self) -> None:
        object.__setattr__(settings, "cloudru_api_key", "secret-test-key")
        object.__setattr__(settings, "cloudru_model_id", "model/test")
        project = create_project("NEXUS Secret", kind="work")
        snapshot = build_nexus_snapshot(int(project["id"]))
        serialized = repr(snapshot)
        self.assertNotIn("secret-test-key", serialized)


if __name__ == "__main__":
    unittest.main()
