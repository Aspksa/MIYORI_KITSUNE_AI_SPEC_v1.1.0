from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_message, connect, create_project, ensure_conversation, init_db,
)
from miyori.conversation_ui import (
    attached_document_context,
    chat_message_page,
    fork_conversation_before_message,
    init_conversation_ui_db,
    list_bookmarked_messages,
    list_chat_conversations,
    search_conversation_messages,
    set_message_bookmark,
    update_chat_conversation,
)


class ChatCapabilitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = settings.database_path
        object.__setattr__(settings, "database_path", Path(self.tmp.name) / "chat.sqlite3")
        init_db()
        init_conversation_ui_db()
        self.a = create_project("Chat test private A")["id"]
        self.b = create_project("Chat test private B")["id"]
        self.ca = ensure_conversation(None, self.a)
        self.cb = ensure_conversation(None, self.b)

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self.previous)
        self.tmp.cleanup()

    def _document(self, project_id: int, filename: str, data: str) -> int:
        with connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents(
                  project_id,filename,stored_path,sha256,size_bytes,created_at
                ) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                """,
                (project_id,filename,filename,
                 (filename + str(project_id)).encode().hex()[:64],len(data)),
            )
            document_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO document_chunks(
                    document_id,chunk_index,content,created_at
                ) VALUES(?,?,?,CURRENT_TIMESTAMP)
                """,
                (document_id,0,data),
            )
            return document_id

    def test_metadata_attached_to_exact_question_and_project(self) -> None:
        a_doc = self._document(self.a,"contract-a.docx","The total is 100.")
        b_doc = self._document(self.b,"secret-b.docx","Secret project B.")
        context, sources = attached_document_context(self.a,[a_doc])
        self.assertEqual(context[0]["filename"],"contract-a.docx")
        self.assertEqual(sources[0]["document_id"],a_doc)
        self.assertIn("100",context[0]["content"])
        with self.assertRaises(ValueError):
            attached_document_context(self.a,[b_doc])
        with self.assertRaises(ValueError):
            attached_document_context(self.a,[a_doc,a_doc])
        with self.assertRaises(ValueError):
            attached_document_context(self.a,[a_doc]*6)

        msg = add_message(self.ca,"user","Check attachment",metadata={"attachments":[a_doc]})
        add_message(self.ca,"assistant","Contract looks consistent.")
        page = chat_message_page(self.a,self.ca)
        self.assertEqual(page["messages"][0]["metadata"]["attachments"],[a_doc])
        self.assertEqual(page["messages"][0]["id"],msg)
        self.assertFalse(page["has_more"])

        names = list_chat_conversations(self.a,"contract-a.docx")
        self.assertEqual([row["id"] for row in names],[self.ca])
        self.assertEqual(search_conversation_messages(self.a,self.ca,"contract-a.docx")[0]["id"],msg)
        self.assertEqual(list_chat_conversations(self.b,"contract-a.docx"),[])
        self.assertEqual(search_conversation_messages(self.b,self.cb,"contract-a.docx"),[])

    def test_fork_preserves_history_without_mutating_original(self) -> None:
        first = add_message(self.ca,"user","Original question?")
        add_message(self.ca,"assistant","Original answer.")
        pivot = add_message(self.ca,"user","Question to edit", metadata={"attachments":[19]})
        reply = add_message(self.ca,"assistant","Not ideal")
        result = fork_conversation_before_message(self.a,self.ca,reply)
        self.assertEqual(result["message"],"Question to edit")
        self.assertEqual(result["attachments"],[19])
        self.assertNotEqual(result["conversation_id"],self.ca)
        fork_page = chat_message_page(self.a,result["conversation_id"])
        self.assertEqual(len(fork_page["messages"]),2)
        self.assertEqual(fork_page["messages"][0]["id"] != first, True)
        original_page = chat_message_page(self.a,self.ca)
        self.assertEqual(len(original_page["messages"]),4)
        with self.assertRaises(LookupError):
            fork_conversation_before_message(self.b,self.ca,pivot)

    def test_page_boundaries_and_browsing(self) -> None:
        for i in range(205):
            add_message(self.ca,"user",f"Row {i}")
        page = chat_message_page(self.a,self.ca,limit=80)
        self.assertEqual(len(page["messages"]),80)
        self.assertTrue(page["has_more"])
        earlier = chat_message_page(
            self.a,self.ca,limit=80,before_id=page["before_id"]
        )
        self.assertEqual(len(earlier["messages"]),80)
        self.assertTrue(earlier["has_more"])
        self.assertLess(earlier["messages"][-1]["id"],page["messages"][0]["id"])
        with self.assertRaises(LookupError):
            chat_message_page(self.b,self.ca)

    def test_bookmarks_titles_pins_and_search_isolated(self) -> None:
        add_message(self.ca,"user","Price question")
        assistant_id = add_message(self.ca,"assistant","Saved answer")
        update_chat_conversation(self.a,self.ca,title="Important",pinned=True)
        items = list_chat_conversations(self.a)
        self.assertTrue(next(x for x in items if x["id"]==self.ca)["pinned"])
        self.assertEqual(list_chat_conversations(self.a,"important")[0]["title"],"Important")
        set_message_bookmark(self.a,self.ca,assistant_id,True)
        self.assertEqual(list_bookmarked_messages(self.a)[0]["message_id"]
                         if "message_id" in list_bookmarked_messages(self.a)[0]
                         else list_bookmarked_messages(self.a)[0]["id"],assistant_id)
        with self.assertRaises(LookupError):
            set_message_bookmark(self.b,self.cb,assistant_id,True)
        with self.assertRaises(LookupError):
            update_chat_conversation(self.b,self.ca,title="Hijacked")
        set_message_bookmark(self.a,self.ca,assistant_id,False)
        self.assertEqual(list_bookmarked_messages(self.a),[])
        init_conversation_ui_db()  # repeatable migration does not overwrite owner data
        self.assertTrue(list_chat_conversations(self.a)[0]["pinned"])


if __name__ == "__main__":
    unittest.main()
