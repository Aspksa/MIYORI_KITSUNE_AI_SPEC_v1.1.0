from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.appearance import (
    MIYORI_APPEARANCE_SCHEMA_VERSION,
    get_appearance_profile,
    init_appearance_db,
    portrait_asset_path,
    remove_portrait_asset,
    save_portrait_asset,
    update_appearance_profile,
)
from miyori.config import settings
from miyori.db import init_db


class MiyoriAppearanceProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_appearance_db()

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_profile_starts_unconfigured_without_system_defaults(self) -> None:
        profile = get_appearance_profile()
        self.assertEqual(profile["schema_version"], MIYORI_APPEARANCE_SCHEMA_VERSION)
        self.assertEqual(profile["state"], "appearance_unconfigured")
        self.assertEqual(profile["completion"], {"selected": 0, "total": 4, "complete": False})
        self.assertEqual(
            profile["selection"],
            {
                "hair_color": None,
                "eye_color": None,
                "tail_count": None,
                "main_outfit": None,
            },
        )
        self.assertFalse(profile["policy"]["system_defaults_allowed"])
        self.assertFalse(profile["policy"]["model_may_choose_owner_fields"])
        self.assertEqual(
            set(profile["persona_open_choices"]),
            {"Цвет волос", "Цвет глаз", "Точное число хвостов", "Основной наряд"},
        )

    def test_partial_and_complete_states_are_derived_from_explicit_choices(self) -> None:
        partial = update_appearance_profile(
            hair_color="серебристые",
            eye_color=None,
            tail_count=None,
            main_outfit=None,
        )
        self.assertEqual(partial["state"], "appearance_partial")
        self.assertEqual(partial["completion"]["selected"], 1)
        self.assertEqual(partial["selection"]["hair_color"], "серебристые")

        complete = update_appearance_profile(
            hair_color="серебристые",
            eye_color="янтарные",
            tail_count=3,
            main_outfit="строгий тёмный костюм",
        )
        self.assertEqual(complete["state"], "appearance_configured")
        self.assertTrue(complete["completion"]["complete"])
        self.assertEqual(complete["selection"]["tail_count"], 3)
        self.assertGreater(complete["revision"], partial["revision"])

    def test_blank_values_clear_choices_and_tail_count_has_no_invented_default(self) -> None:
        update_appearance_profile(
            hair_color="рыжие",
            eye_color="зелёные",
            tail_count=2,
            main_outfit="платье",
        )
        cleared = update_appearance_profile(
            hair_color="  ",
            eye_color=None,
            tail_count=None,
            main_outfit="",
        )
        self.assertEqual(cleared["state"], "appearance_unconfigured")
        self.assertIsNone(cleared["selection"]["hair_color"])
        self.assertIsNone(cleared["selection"]["tail_count"])

        with self.assertRaises(ValueError):
            update_appearance_profile(
                hair_color=None,
                eye_color=None,
                tail_count=0,
                main_outfit=None,
            )

    def test_static_portrait_asset_is_explicitly_non_dynamic(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"test-static-image"
        profile = save_portrait_asset(png, "image/png")
        asset = profile["asset"]
        self.assertEqual(asset["kind"], "static_portrait")
        self.assertEqual(asset["url"], "/api/miyori/appearance/portrait")
        self.assertFalse(asset["supports_dynamic_pose"])
        self.assertFalse(asset["supports_expression"])
        self.assertTrue(asset["sha256"])
        self.assertEqual(asset["size_bytes"], len(png))
        self.assertIsNotNone(portrait_asset_path())

        removed = remove_portrait_asset()
        self.assertIsNone(removed["asset"]["kind"])
        self.assertIsNone(portrait_asset_path())

    def test_spoofed_image_mime_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_portrait_asset(b"<html>not an image</html>", "image/png")
        with self.assertRaises(ValueError):
            save_portrait_asset(b"RIFFxxxxNOPE", "image/webp")
        with self.assertRaises(ValueError):
            save_portrait_asset(b"\x89PNG\r\n\x1a\n", "image/gif")


if __name__ == "__main__":
    unittest.main()
