from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from miyori.config import settings
from miyori.db import create_project, init_db


class SafeChatForksTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_database=settings.database_path
        root=Path(self.temp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"data.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        self.project_id=int(create_project("Safe Fork Test")["id"])

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_database)
        self.temp.cleanup()

    def test_fork_replies_never_repeat_tools_or_recapture_memory(self):
        import app as server
        request=server.ChatRequest(
            project_id=self.project_id,
            message="Создай файл test.txt и запиши в него информацию",
            request_id="test-fork-no-tool-001",
            read_only=True,
        )
        with patch.object(server,"run_agent",new_callable=AsyncMock) as agent, \
             patch.object(server,"_build_agent_response",new_callable=AsyncMock) as answer, \
             patch.object(server,"maybe_capture_user_memory") as capture, \
             patch.object(server,"capture_user_claims") as claims:
            answer.return_value={"ok":True}
            asyncio.run(server.send_message(request))
            route=agent.await_args.args[3]
            self.assertFalse(route.use_tools,"Fork must never execute write tools.")
            self.assertIn("safe_read_only_fork",route.reasons)
            capture.assert_not_called()
            claims.assert_not_called()

        # The request ID cannot later be reused to authorize write tools.
        with self.assertRaises(HTTPException) as error:
            asyncio.run(server.send_message(request.model_copy(update={"read_only":False})))
        self.assertEqual(error.exception.status_code,409)

    def test_normal_new_request_preserves_explicit_action_flow(self):
        import app as server
        request=server.ChatRequest(
            project_id=self.project_id,
            message="Создай файл test.txt",
            request_id="test-normal-tools-001",
            read_only=False,
        )
        with patch.object(server,"run_agent",new_callable=AsyncMock) as agent, \
             patch.object(server,"_build_agent_response",new_callable=AsyncMock) as answer, \
             patch.object(server,"maybe_capture_user_memory",return_value=None), \
             patch.object(server,"capture_user_claims",return_value=[]):
            answer.return_value={"ok":True}
            asyncio.run(server.send_message(request))
            route=agent.await_args.args[3]
            self.assertTrue(route.use_tools,"New user actions must remain functional.")


if __name__=="__main__":
    unittest.main()
