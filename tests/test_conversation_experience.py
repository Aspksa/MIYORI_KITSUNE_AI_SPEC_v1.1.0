from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from miyori.config import settings
from miyori.conversation_experience import (
    assign_topic,
    complete_schedule,
    conversation_snapshot,
    create_folder,
    create_topic,
    create_voice_note,
    delete_voice_note,
    due_schedules,
    filter_conversation_ids,
    folder_snapshot,
    init_conversation_experience_db,
    mark_read,
    pinned_chat_context,
    remember_message_candidate,
    reply_context,
    route_message,
    save_checklist,
    schedule_message,
    set_conversation_folder,
    set_pin,
    set_reaction,
    set_tags,
    smart_search,
    topic_recent_messages,
    validate_topic,
    voice_note,
    voice_note_path,
)
from miyori.conversation_ui import init_conversation_ui_db, set_message_bookmark
from miyori.db import (
    add_message,
    create_project,
    ensure_conversation,
    init_db,
    list_memory_facts,
)


class ConversationExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = settings.data_dir
        self.old_db = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(
            settings, "database_path", root / "data" / "conversation-ux.sqlite3"
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_conversation_ui_db()
        init_conversation_experience_db()
        self.project = int(create_project("UX")["id"])
        self.other = int(create_project("Other")["id"])
        self.conversation = ensure_conversation(None, self.project)
        self.other_conversation = ensure_conversation(None, self.other)
        self.user = add_message(self.conversation, "user", "Проверь договор №42")
        self.answer = add_message(
            self.conversation,
            "assistant",
            "Нужно проверить сумму и дату.\n- Сумма\n- Дата",
        )

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_dir)
        object.__setattr__(settings, "database_path", self.old_db)
        self.tmp.cleanup()

    def test_topics_quote_and_project_ownership(self) -> None:
        topic = create_topic(self.project, self.conversation, "Договоры")
        self.assertEqual(
            validate_topic(self.project, self.conversation, topic["id"]),
            topic["id"],
        )
        assign_topic(self.project, self.conversation, self.user, topic["id"])
        scoped = topic_recent_messages(
            self.project, self.conversation, topic["id"]
        )
        self.assertEqual([item["content"] for item in scoped], ["Проверь договор №42"])
        set_pin(self.project, self.conversation, self.answer, True)
        pinned = pinned_chat_context(self.project, self.conversation)
        self.assertEqual(pinned[0]["message_id"], self.answer)
        quote = reply_context(
            self.project, self.conversation, self.answer, "проверить сумму"
        )
        self.assertEqual(quote["message_id"], self.answer)
        self.assertEqual(quote["quote"], "проверить сумму")
        with self.assertRaises((LookupError, ValueError)):
            reply_context(self.other, self.other_conversation, self.answer, "")

    def test_tags_pins_reactions_checklist_and_snapshot(self) -> None:
        self.assertEqual(
            set_tags(
                self.project, self.conversation, self.answer,
                ["Важно", "договор", "важно"],
            ),
            ["важно", "договор"],
        )
        set_pin(self.project, self.conversation, self.answer, True)
        reactions = set_reaction(
            self.project, self.conversation, self.answer, "verify", True
        )
        self.assertIn("verify", reactions)
        items = save_checklist(
            self.project,
            self.conversation,
            self.answer,
            [{"text": "Сумма", "done": False}, {"text": "Дата", "done": True}],
        )
        self.assertEqual(len(items), 2)
        snapshot = conversation_snapshot(self.project, self.conversation)
        self.assertEqual(snapshot["pins"][0]["message_id"], self.answer)
        self.assertIn("важно", snapshot["tags"][str(self.answer)])
        self.assertIn("verify", snapshot["reactions"][str(self.answer)])
        self.assertTrue(
            snapshot["checklists"][str(self.answer)]["items"][1]["done"]
        )

    def test_saved_folders_unread_and_routing(self) -> None:
        set_message_bookmark(
            self.project, self.conversation, self.answer, True
        )
        folder = create_folder(self.project, "Работа")
        set_conversation_folder(
            self.project, self.conversation, folder["id"], True
        )
        folders = folder_snapshot(self.project)
        self.assertEqual(folders["system"]["saved"], 1)
        self.assertIn(
            self.conversation,
            filter_conversation_ids(
                self.project, f"custom:{folder['id']}"
            ),
        )
        self.assertIn(
            self.conversation,
            filter_conversation_ids(self.project, "unread"),
        )
        mark_read(self.project, self.conversation, self.answer)
        self.assertNotIn(
            self.conversation,
            filter_conversation_ids(self.project, "unread"),
        )
        routed = route_message(
            self.project, self.conversation, self.answer,
            "knowledge", {"reason": "owner"},
        )
        self.assertEqual(routed["destination"], "knowledge")

    def test_memory_reaction_stays_candidate(self) -> None:
        fact = remember_message_candidate(
            self.project, self.conversation, self.answer,
            "Сумму договора нужно перепроверить.",
        )
        self.assertEqual(fact["status"], "candidate")
        memory = list_memory_facts(self.project)
        saved = next(item for item in memory if item["id"] == fact["id"])
        self.assertEqual(saved["message_id"], self.answer)

    def test_schedule_and_repeat_contract(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        scheduled = schedule_message(
            self.project, self.conversation, "Проверить договор",
            past, "daily", True,
        )
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        future_item = schedule_message(
            self.project, self.conversation, "Не сейчас",
            future, "none", False,
        )
        due = due_schedules(self.project)
        self.assertEqual(due[0]["id"], scheduled["id"])
        self.assertNotIn(future_item["id"], [item["id"] for item in due])
        updated = complete_schedule(self.project, scheduled["id"])
        self.assertEqual(updated["status"], "scheduled")
        self.assertEqual(updated["repeat_mode"], "daily")

    def test_voice_note_is_project_scoped(self) -> None:
        note = create_voice_note(
            self.project, b"voice-bytes", "audio/webm", 1200
        )
        self.assertEqual(
            voice_note(self.project, note["id"])["duration_ms"], 1200
        )
        resolved = voice_note_path(self.project, note["id"])
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved[0].exists())
        draft = create_voice_note(
            self.project, b"draft-voice", "audio/webm", 500
        )
        self.assertTrue(delete_voice_note(self.project, draft["id"]))
        self.assertIsNone(voice_note_path(self.project, draft["id"]))
        sent = create_voice_note(
            self.project, b"sent-voice", "audio/webm", 900
        )
        add_message(
            self.conversation, "user", "Voice",
            metadata={"voice_note_id": sent["id"]},
        )
        self.assertFalse(delete_voice_note(self.project, sent["id"]))
        self.assertIsNotNone(voice_note_path(self.project, sent["id"]))
        with self.assertRaises(ValueError):
            voice_note(self.other, note["id"])

    def test_smart_search_is_honest_about_embeddings(self) -> None:
        result = smart_search(
            self.project, "договор сумма",
            conversation_id=self.conversation, scope="conversation",
        )
        self.assertFalse(result["semantic_embeddings"])
        self.assertEqual(result["mode"], "chat_ranked_lexical")
        self.assertTrue(any(item["kind"] == "chat" for item in result["matches"]))


if __name__ == "__main__":
    unittest.main()
