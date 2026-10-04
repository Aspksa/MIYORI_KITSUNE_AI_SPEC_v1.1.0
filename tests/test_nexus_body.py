from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from miyori.config import settings
from miyori.db import create_project, init_db
from miyori.document_intelligence import init_document_intelligence_db
from miyori.epistemic import init_epistemic_db
from miyori.nexus_body import (
    NEXUS_BODY_SCHEMA_VERSION,
    build_nexus_body,
)


class NexusDigitalBodyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_epistemic_db()
        self.project = create_project("Digital Body", kind="home")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _presence(self, mode: str) -> dict:
        return {
            "schema_version": "1.0.0",
            "project": {
                "id": self.project_id,
                "name": self.project["name"],
                "kind": self.project["kind"],
            },
            "mode": mode,
            "headline": "State",
            "detail": "Detail",
            "attention": "none",
            "reasons": [],
        }

    def test_real_body_build_stays_downstream_of_presence_without_recursion(self) -> None:
        body = build_nexus_body(self.project_id)
        self.assertEqual(body["schema_version"], NEXUS_BODY_SCHEMA_VERSION)
        self.assertEqual(body["runtime"]["source"], "nexus_presence")
        self.assertEqual(body["runtime"]["presence_mode"], "degraded")
        self.assertEqual(body["state"], "degraded")

    def test_persona_canon_is_preserved_without_inventing_open_choices(self) -> None:
        with patch("miyori.nexus_body.build_nexus_presence", return_value=self._presence("ready")):
            body = build_nexus_body(self.project_id)

        self.assertEqual(body["schema_version"], NEXUS_BODY_SCHEMA_VERSION)
        appearance = body["appearance"]
        self.assertEqual(appearance["name"], "Миёри")
        self.assertEqual(appearance["age_years"], 25)
        self.assertTrue(appearance["is_adult"])
        self.assertIn("Лисьи ушки", appearance["confirmed"])
        self.assertIn("Пушистые хвосты", appearance["confirmed"])
        self.assertIn("Выразительный взгляд", appearance["confirmed"])
        self.assertEqual(
            set(appearance["open_for_owner_choice"]),
            {"Цвет волос", "Цвет глаз", "Точное число хвостов", "Основной наряд"},
        )
        self.assertEqual(appearance["configuration_state"], "appearance_unconfigured")
        self.assertIsNone(appearance["final_portrait_asset"])

    def test_server_body_state_is_derived_from_presence(self) -> None:
        cases = {
            "ready": ("rest", "neutral", "still"),
            "working": ("focus", "focused", "working"),
            "verifying": ("inspect", "focused", "verify"),
            "waiting": ("listen", "attentive", "hold"),
            "recovery": ("inspect", "alert", "recover"),
            "attention": ("alert", "alert", "attention"),
            "degraded": ("restrained", "neutral", "limited"),
        }
        for mode, expected in cases.items():
            with self.subTest(mode=mode):
                with patch(
                    "miyori.nexus_body.build_nexus_presence",
                    return_value=self._presence(mode),
                ):
                    body = build_nexus_body(self.project_id)
                self.assertEqual(body["state"], mode)
                presentation = body["presentation"]
                self.assertEqual(
                    (presentation["pose"], presentation["expression"], presentation["gesture"]),
                    expected,
                )
                self.assertEqual(body["runtime"]["source"], "nexus_presence")

    def test_unknown_presence_mode_fails_closed_to_degraded(self) -> None:
        with patch(
            "miyori.nexus_body.build_nexus_presence",
            return_value=self._presence("invented-state"),
        ):
            body = build_nexus_body(self.project_id)
        self.assertEqual(body["state"], "degraded")
        self.assertEqual(body["presentation"]["gesture"], "limited")

    def test_local_overrides_are_explicit_runtime_states_only(self) -> None:
        with patch("miyori.nexus_body.build_nexus_presence", return_value=self._presence("ready")):
            body = build_nexus_body(self.project_id)

        local = body["local_override_contract"]
        self.assertEqual(
            local["allowed_states"],
            [
                "idle",
                "thinking",
                "listening",
                "transcribing",
                "speaking",
                "interrupted",
                "voice_error",
            ],
        )
        self.assertTrue(local["idle_returns_to_server_state"])
        self.assertEqual(local["voice_state_source"], "miyori:voice-state")
        self.assertEqual(local["thinking_state_source"], "miyori:interaction-state")
        self.assertNotIn("idle", local["presentations"])

    def test_motion_policy_forbids_fake_liveness_and_sentiment_guessing(self) -> None:
        with patch("miyori.nexus_body.build_nexus_presence", return_value=self._presence("ready")):
            body = build_nexus_body(self.project_id)

        policy = body["motion_policy"]
        self.assertFalse(policy["random_liveness_allowed"])
        self.assertFalse(policy["timer_idle_animation_allowed"])
        self.assertFalse(policy["sentiment_to_expression_allowed"])
        self.assertFalse(policy["model_authored_motion_allowed"])
        self.assertTrue(policy["state_transition_motion_allowed"])
        self.assertTrue(policy["reduced_motion_must_be_respected"])

    def test_render_policy_keeps_owner_choices_open(self) -> None:
        with patch("miyori.nexus_body.build_nexus_presence", return_value=self._presence("ready")):
            body = build_nexus_body(self.project_id)

        policy = body["render_policy"]
        self.assertTrue(policy["neutral_shell_until_owner_appearance_choice"])
        self.assertFalse(policy["invent_open_appearance_choices_allowed"])
        self.assertFalse(policy["tail_count_may_be_invented"])
        self.assertFalse(policy["hair_color_may_be_invented"])
        self.assertFalse(policy["eye_color_may_be_invented"])
        self.assertFalse(policy["outfit_may_be_invented"])
        self.assertEqual(
            policy["body_state_source"],
            "presence_plus_explicit_local_runtime",
        )


if __name__ == "__main__":
    unittest.main()
