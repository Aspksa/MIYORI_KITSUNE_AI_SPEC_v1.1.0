from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_memory_fact,
    add_message,
    conversation_messages,
    create_project,
    ensure_conversation,
    init_db,
    maybe_capture_user_memory,
    search_verified_memory,
)


class MemoryLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_database_path = settings.database_path
        object.__setattr__(settings, "database_path", Path(self.tmp.name) / "memory-v2.sqlite3")
        init_db()
        self.p1 = create_project("Memory A")
        self.p2 = create_project("Memory B")

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_user_memory_is_visible_across_projects_but_project_memory_is_not(self) -> None:
        add_memory_fact(
            self.p1["id"],
            "Пользователь предпочитает компактный интерфейс.",
            status="verified",
            memory_scope="user",
            memory_kind="preference",
            salience=0.9,
        )
        add_memory_fact(
            self.p1["id"],
            "В проекте Memory A используется кодовое имя Альфа.",
            status="verified",
            memory_scope="project",
            memory_kind="fact",
        )

        rows = search_verified_memory(
            self.p2["id"],
            "Какой интерфейс предпочитает пользователь и какое кодовое имя?",
            limit=10,
        )
        texts = [item["statement"] for item in rows]
        self.assertTrue(any("компактный интерфейс" in text for text in texts))
        self.assertFalse(any("Альфа" in text for text in texts))

    def test_ordinary_message_is_not_long_term_memory(self) -> None:
        conversation_id = ensure_conversation(None, self.p1["id"])
        message_id = add_message(conversation_id, "user", "Сегодня я просмотрел договор.")
        captured = maybe_capture_user_memory(
            self.p1["id"],
            conversation_id,
            message_id,
            "Сегодня я просмотрел договор.",
        )
        self.assertIsNone(captured)

    def test_explicit_preference_becomes_verified_user_memory(self) -> None:
        conversation_id = ensure_conversation(None, self.p1["id"])
        text = "Я предпочитаю компактный интерфейс"
        message_id = add_message(conversation_id, "user", text)
        captured = maybe_capture_user_memory(
            self.p1["id"],
            conversation_id,
            message_id,
            text,
        )
        self.assertIsNotNone(captured)
        self.assertEqual(captured["status"], "verified")
        self.assertEqual(captured["memory_scope"], "user")
        self.assertEqual(captured["memory_kind"], "preference")

    def test_assistant_sources_are_persisted_with_message(self) -> None:
        conversation_id = ensure_conversation(None, self.p1["id"])
        add_message(
            conversation_id,
            "assistant",
            "Ответ по документу.",
            metadata={"sources": [{"title": "contract.pdf", "document_id": 7}]},
        )
        rows = conversation_messages(conversation_id, self.p1["id"])
        self.assertEqual(rows[0]["metadata"]["sources"][0]["title"], "contract.pdf")


if __name__ == "__main__":
    unittest.main()
