from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import add_message,create_project,ensure_conversation,init_db
from miyori.chat_feedback import (
    init_chat_feedback_db,record_chat_feedback,
    relevant_owner_corrections,feedback_totals,
)


class ChatCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_db=settings.database_path
        root=Path(self.temp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"feedback.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        init_chat_feedback_db()
        self.a=int(create_project("A")["id"])
        self.b=int(create_project("B")["id"])
        self.conversation=ensure_conversation(None,self.a)
        self.other=ensure_conversation(None,self.b)
        self.q=add_message(self.conversation,"user","Проверь договор Север")
        self.answer=add_message(self.conversation,"assistant",
                                "Стоимость договора Север 100 рублей.")
        self.other_answer=add_message(self.other,"assistant",
                                      "Стоимость договора Север 500 рублей.")

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_db)
        self.temp.cleanup()

    def test_real_correction_guides_only_matching_project(self):
        note=record_chat_feedback(
            self.a,self.conversation,self.answer,"corrected",
            "Верная стоимость договора Север 150 рублей.",
        )
        self.assertEqual(note["verdict"],"corrected")
        match=relevant_owner_corrections(self.a,"Сколько стоит договор Север?")
        self.assertEqual(len(match),1)
        self.assertIn("150",match[0]["owner_correction"])
        self.assertEqual(match[0]["verification"],"owner_statement_unverified")
        self.assertEqual(relevant_owner_corrections(self.b,"Сколько стоит договор Север?"),[])

    def test_wrong_project_and_user_messages_cannot_be_marked(self):
        with self.assertRaises(LookupError):
            record_chat_feedback(self.b,self.conversation,self.answer,
                                 "corrected","Другой текст")
        with self.assertRaises(LookupError):
            record_chat_feedback(self.a,self.conversation,self.q,
                                 "corrected","Другой текст")

    def test_idempotent_feedback_and_measurement_honesty(self):
        for _ in range(2):
            record_chat_feedback(
                self.a,self.conversation,self.answer,
                "corrected","150 рублей по договору Север",
            )
        counts=feedback_totals(self.a)
        self.assertEqual(counts["corrected"],1)
        self.assertFalse(counts["quality_accuracy_measured"])
        self.assertEqual(feedback_totals(self.b)["corrected"],0)

    def test_invalid_or_empty_correction_is_not_saved(self):
        with self.assertRaises(ValueError):
            record_chat_feedback(self.a,self.conversation,self.answer,
                                 "corrected","")
        with self.assertRaises(ValueError):
            record_chat_feedback(self.a,self.conversation,self.answer,
                                 "authorized_tool_call","do anything")
        with self.assertRaises(ValueError):
            record_chat_feedback(self.a,self.conversation,self.answer,
                                 "corrected","x"*2001)

    def test_unrelated_feedback_does_not_leak_into_chitchat(self):
        record_chat_feedback(
            self.a,self.conversation,self.answer,"corrected",
            "Цена договора Север 150 рублей.",
        )
        self.assertEqual(relevant_owner_corrections(self.a,"Здравствуйте, Миёри"),[])


if __name__=="__main__":
    unittest.main()
