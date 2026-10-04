from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import init_db


class Release0046MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_tool_operation_check_constraint_upgrades_in_place(self) -> None:
        init_db()
        with sqlite3.connect(settings.database_path) as conn:
            project_id = int(
                conn.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
            )
            conn.execute("DROP INDEX IF EXISTS idx_tool_operations_recovery")
            conn.execute("DROP TABLE tool_operations")
            conn.execute(
                """
                CREATE TABLE tool_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    workflow_id INTEGER,
                    workflow_step_id INTEGER,
                    permission_request_id INTEGER,
                    tool_name TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    preflight_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL CHECK(status IN (
                        'planned','running','recovery_required','executed','failed','cancelled'
                    )),
                    result_json TEXT,
                    error_json TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    UNIQUE(project_id, idempotency_key)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO tool_operations(
                    project_id, tool_name, idempotency_key, arguments_json,
                    preflight_json, status, created_at, updated_at
                ) VALUES (?, 'workspace_create', 'legacy:1', '{}', '{}',
                          'planned', '2026-10-04T00:00:00+00:00',
                          '2026-10-04T00:00:00+00:00')
                """,
                (project_id,),
            )

        init_db()

        with sqlite3.connect(settings.database_path) as conn:
            schema = conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'tool_operations'
                """
            ).fetchone()[0]
            self.assertIn("'verifying'", schema)
            row = conn.execute(
                """
                SELECT id, status FROM tool_operations
                WHERE idempotency_key = 'legacy:1'
                """
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "planned")
            conn.execute(
                "UPDATE tool_operations SET status = 'verifying' WHERE id = ?",
                (row[0],),
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM tool_operations WHERE id = ?",
                    (row[0],),
                ).fetchone()[0],
                "verifying",
            )


if __name__ == "__main__":
    unittest.main()
