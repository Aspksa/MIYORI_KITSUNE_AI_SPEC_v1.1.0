from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.epistemic import (
    add_evidence,
    capture_user_claims,
    create_claim,
    create_source,
    epistemic_snapshot,
    get_claim,
    init_epistemic_db,
)


class EpistemicCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_database_path = settings.database_path
        self._tmp = tempfile.TemporaryDirectory()
        object.__setattr__(settings, "database_path", Path(self._tmp.name) / "test.sqlite3")
        init_db()
        init_epistemic_db()
        self.project = create_project("Epistemic Test")

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self._old_database_path)
        self._tmp.cleanup()

    def test_user_fact_stays_candidate_without_independent_evidence(self) -> None:
        claims = capture_user_claims(
            self.project["id"],
            conversation_id=1,
            message_id=1,
            text="Python 4 уже вышел.",
        )
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_type"], "fact")
        self.assertEqual(claims[0]["status"], "candidate")

    def test_direct_user_preference_can_be_verified(self) -> None:
        claims = capture_user_claims(
            self.project["id"],
            conversation_id=1,
            message_id=2,
            text="Мне нравится компактный интерфейс.",
        )
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_type"], "preference")
        self.assertEqual(claims[0]["status"], "verified")
        self.assertEqual(claims[0]["confidence"], 1.0)

    def test_two_independent_sources_verify_fact(self) -> None:
        claim = create_claim(self.project["id"], "Тестовый внешний факт.")
        source_a = create_source(
            self.project["id"], "external",
            title="Source A", quality=0.9, independent_group="publisher:a",
        )
        source_b = create_source(
            self.project["id"], "external",
            title="Source B", quality=0.9, independent_group="publisher:b",
        )
        add_evidence(self.project["id"], claim["id"], source_a["id"], "supports", weight=1.0)
        add_evidence(self.project["id"], claim["id"], source_b["id"], "supports", weight=1.0)
        refreshed = get_claim(self.project["id"], claim["id"])
        self.assertEqual(refreshed["status"], "verified")
        self.assertGreaterEqual(refreshed["confidence"], 0.8)

    def test_material_conflict_becomes_disputed(self) -> None:
        claim = create_claim(self.project["id"], "Проверяемое утверждение.")
        support = create_source(
            self.project["id"], "external",
            title="Support", quality=1.0, independent_group="support",
        )
        contradict = create_source(
            self.project["id"], "external",
            title="Contradict", quality=1.0, independent_group="contradict",
        )
        add_evidence(self.project["id"], claim["id"], support["id"], "supports", weight=1.0)
        add_evidence(self.project["id"], claim["id"], contradict["id"], "contradicts", weight=1.0)
        refreshed = get_claim(self.project["id"], claim["id"])
        self.assertEqual(refreshed["status"], "disputed")

    def test_snapshot_reports_real_counts(self) -> None:
        create_claim(self.project["id"], "Один кандидат.")
        snapshot = epistemic_snapshot(self.project["id"])
        self.assertEqual(snapshot["claims"]["candidate"], 1)
        self.assertEqual(snapshot["sources"], 0)


if __name__ == "__main__":
    unittest.main()
