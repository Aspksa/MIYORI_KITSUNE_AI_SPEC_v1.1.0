from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.epistemic import (
    claim_assessment,
    create_claim,
    get_claim,
    init_epistemic_db,
)


class EpistemicAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_database_path = settings.database_path
        object.__setattr__(settings, "database_path", Path(self.tmp.name) / "epistemic-v2.sqlite3")
        init_db()
        init_epistemic_db()
        self.project = create_project("Epistemic v2")

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_human_assessment_labels(self) -> None:
        self.assertEqual(claim_assessment("verified", 0.95), "Подтверждено")
        self.assertEqual(claim_assessment("supported", 0.7), "Вероятно")
        self.assertEqual(claim_assessment("candidate", 0.2), "Недостаточно данных")
        self.assertEqual(claim_assessment("verified", 0.95, 1), "Есть противоречия")

    def test_numeric_conflict_is_visible(self) -> None:
        first = create_claim(
            self.project["id"],
            "Сумма договора Восток составляет 100000 рублей.",
            claim_type="fact",
            status="verified",
            confidence=0.95,
        )
        second = create_claim(
            self.project["id"],
            "Сумма договора Восток составляет 120000 рублей.",
            claim_type="fact",
            status="verified",
            confidence=0.95,
        )
        refreshed = get_claim(self.project["id"], second["id"])
        self.assertTrue(refreshed["contradictions"])
        self.assertEqual(refreshed["assessment"], "Есть противоречия")


if __name__ == "__main__":
    unittest.main()
