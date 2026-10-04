from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.nexus_voice import (
    NEXUS_VOICE_SCHEMA_VERSION,
    VOICE_STATES,
    build_nexus_voice_contract,
)


class NexusVoiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("NEXUS Voice", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_voice_contract_is_explicit_and_permission_safe(self) -> None:
        payload = build_nexus_voice_contract(self.project_id)
        self.assertEqual(payload["schema_version"], NEXUS_VOICE_SCHEMA_VERSION)
        self.assertEqual(set(payload["protocol"]["states"]), set(VOICE_STATES))
        self.assertTrue(payload["protocol"]["final_transcript_required_before_submit"])
        self.assertTrue(payload["protocol"]["interim_transcript_is_ephemeral"])
        self.assertTrue(payload["permissions"]["microphone_requires_explicit_user_gesture"])
        self.assertFalse(payload["permissions"]["background_recording_allowed"])
        self.assertFalse(payload["safety"]["voice_can_bypass_action_permissions"])
        self.assertFalse(payload["safety"]["voice_can_auto_approve_actions"])
        self.assertFalse(payload["safety"]["voice_can_auto_execute_write_tools"])
        self.assertTrue(payload["safety"]["final_transcript_uses_existing_chat_pipeline"])
        self.assertFalse(payload["transport"]["server_audio_storage"])
        self.assertTrue(payload["transport"]["desktop_transport_replaceable"])

    def test_missing_project_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_nexus_voice_contract(999999)


if __name__ == "__main__":
    unittest.main()
