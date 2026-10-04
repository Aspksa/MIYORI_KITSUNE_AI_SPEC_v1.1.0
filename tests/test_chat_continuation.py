from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from miyori.config import settings
from miyori.db import init_db,create_project,create_task
from miyori.nexus_actions import build_nexus_action_center


class ChatContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_db=settings.database_path
        root=Path(self.temp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"state.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        self.first=int(create_project("First")["id"])
        self.second=int(create_project("Second")["id"])

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_db)
        self.temp.cleanup()

    def test_task_state_is_real_project_scoped_and_persisted(self):
        create_task(self.first,"document_question",{"document_id":9})
        active=build_nexus_action_center(self.first)
        other=build_nexus_action_center(self.second)
        self.assertEqual(len([c for c in active["actions"] if c["kind"]=="task"]),1)
        self.assertFalse([c for c in other["actions"] if c["kind"]=="task"])
        again=build_nexus_action_center(self.first)
        self.assertEqual(active["counts"]["active"],again["counts"]["active"])
        self.assertFalse(active["semantics"]["speculative_progress_allowed"])
        self.assertIn("agent_workflows",active["semantics"]["authoritative_sources"])


if __name__=="__main__":
    unittest.main()
