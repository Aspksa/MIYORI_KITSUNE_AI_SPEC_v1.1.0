from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.chat_feedback import init_chat_feedback_db, record_chat_feedback
from miyori.chat_metrics import (
    chat_quality_summary,
    init_chat_metrics_db,
    store_model_usage,
)
from miyori.config import settings
from miyori.db import add_message, create_project, ensure_conversation, init_db


class ChatQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = settings.data_dir
        self.old_db = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "quality.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_chat_metrics_db()
        init_chat_feedback_db()
        self.project_id = int(create_project("Quality")["id"])
        self.other_id = int(create_project("Other")["id"])
        self.conversation_id = ensure_conversation(None, self.project_id)

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_dir)
        object.__setattr__(settings, "database_path", self.old_db)
        self.tmp.cleanup()

    def test_summary_counts_only_measured_project_signals(self) -> None:
        add_message(self.conversation_id, "user", "Сколько?")
        answer_id = add_message(
            self.conversation_id,
            "assistant",
            "100 рублей",
            metadata={
                "sources": [{"title": "Договор"}],
                "diagnostics": {
                    "evidence": {"status": "sources_available_not_fact_checked"},
                    "numeric_check": {
                        "status": "checked_numbers",
                        "claims_seen": 2,
                        "matching_source": 1,
                        "missing_source": 1,
                    },
                },
            },
        )
        record_chat_feedback(
            self.project_id,
            self.conversation_id,
            answer_id,
            "corrected",
            "Верная сумма 150 рублей.",
        )
        store_model_usage(
            self.project_id,
            answer_id,
            {"model": "test", "latency_ms": 240, "total_tokens": 20},
        )

        report = chat_quality_summary(self.project_id, days=30)
        self.assertEqual(report["assistant_responses"], 1)
        self.assertEqual(report["responses_with_sources"], 1)
        self.assertEqual(report["numeric_claims_seen"], 2)
        self.assertEqual(report["numeric_claims_missing_source"], 1)
        self.assertEqual(report["feedback"]["corrected"], 1)
        self.assertEqual(report["average_latency_ms"], 240)
        self.assertFalse(report["quality_accuracy_measured"])

        other = chat_quality_summary(self.other_id, days=30)
        self.assertEqual(other["assistant_responses"], 0)
        self.assertEqual(other["feedback"]["corrected"], 0)


if __name__ == "__main__":
    unittest.main()
