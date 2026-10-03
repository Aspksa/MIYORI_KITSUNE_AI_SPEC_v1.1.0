from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import init_db


class Release0038MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_database_path = settings.database_path
        self.path = Path(self.tmp.name) / "legacy.sqlite3"
        object.__setattr__(settings, "database_path", self.path)

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_0037_messages_and_permissions_upgrade_in_place(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(
                """
                CREATE TABLE conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Новый разговор',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE permission_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    executed_at TEXT
                );
                """
            )

        # Must not fail while the legacy messages table still lacks client_request_id.
        init_db()

        with sqlite3.connect(self.path) as conn:
            message_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            }
            permission_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(permission_requests)").fetchall()
            }
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            indexes = {
                row[1]
                for row in conn.execute("PRAGMA index_list(messages)").fetchall()
            }

        self.assertIn("client_request_id", message_columns)
        self.assertIn("workflow_id", permission_columns)
        self.assertIn("workflow_step_id", permission_columns)
        self.assertIn("tool_operation_id", permission_columns)
        self.assertIn("idempotency_key", permission_columns)
        self.assertIn("preview_json", permission_columns)
        self.assertIn("agent_workflows", tables)
        self.assertIn("workflow_steps", tables)
        self.assertIn("tool_operations", tables)
        self.assertIn("audit_events", tables)
        self.assertIn("idx_messages_client_request", indexes)


if __name__ == "__main__":
    unittest.main()
