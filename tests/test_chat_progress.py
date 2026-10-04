from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.chat_progress import (
    get_chat_progress,
    init_chat_progress_db,
    set_chat_progress,
)
from miyori.config import settings
from miyori.db import create_project, init_db


class ChatProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = settings.data_dir
        self.old_db = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "progress.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_chat_progress_db()
        self.a = int(create_project("A")["id"])
        self.b = int(create_project("B")["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_dir)
        object.__setattr__(settings, "database_path", self.old_db)
        self.tmp.cleanup()

    def test_progress_is_request_and_project_scoped(self) -> None:
        set_chat_progress(self.a, "req-12345678", "accepted", "Принято")
        set_chat_progress(self.a, "req-12345678", "retrieving", "Поиск")
        current = get_chat_progress(self.a, "req-12345678")
        self.assertEqual(current["stage"], "retrieving")
        self.assertEqual(current["detail"], "Поиск")
        self.assertIsNone(get_chat_progress(self.b, "req-12345678"))

    def test_unknown_stage_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            set_chat_progress(self.a, "req-12345678", "pretending", "Нет")


if __name__ == "__main__":
    unittest.main()
