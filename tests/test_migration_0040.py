from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db


class Release0040MigrationTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_0039_document_windows_upgrade_in_place(self) -> None:
        with sqlite3.connect(settings.database_path) as conn:
            conn.executescript(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY
                );
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY
                );
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY
                );

                CREATE TABLE document_analysis_windows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    document_id INTEGER NOT NULL,
                    window_index INTEGER NOT NULL,
                    start_node_index INTEGER NOT NULL,
                    end_node_index INTEGER NOT NULL,
                    source_chars INTEGER NOT NULL,
                    locator_start TEXT,
                    locator_end TEXT,
                    summary TEXT,
                    analysis_json TEXT NOT NULL DEFAULT '{}',
                    model_id TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(document_id, window_index)
                );

                INSERT INTO document_analysis_windows(
                    project_id, document_id, window_index,
                    start_node_index, end_node_index, source_chars,
                    locator_start, locator_end, summary,
                    analysis_json, model_id, created_at
                ) VALUES (
                    1, 7, 1, 0, 2, 1234,
                    'text:lines:1-20', 'text:lines:21-40',
                    'old window', '{}', 'model-old',
                    '2026-10-03T00:00:00+00:00'
                );
                """
            )

        init_document_intelligence_db()
        init_document_questions_db()

        with sqlite3.connect(settings.database_path) as conn:
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(document_analysis_windows)"
                ).fetchall()
            }
            self.assertIn("source_fingerprint", columns)

            old = conn.execute(
                """
                SELECT summary, source_chars, source_fingerprint
                FROM document_analysis_windows
                WHERE document_id = 7 AND window_index = 1
                """
            ).fetchone()
            self.assertEqual(old[0], "old window")
            self.assertEqual(old[1], 1234)
            self.assertEqual(old[2], "")

            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("document_questions", tables)
            self.assertIn("document_question_windows", tables)


if __name__ == "__main__":
    unittest.main()
