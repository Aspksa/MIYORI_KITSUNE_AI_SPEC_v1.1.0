from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.account import cloudru_profile, save_cloudru_profile
from miyori.config import settings


class CloudRuAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = settings.root_dir
        self.old_key = settings.cloudru_api_key
        self.old_base = settings.cloudru_base_url
        self.old_model = settings.cloudru_model_id
        object.__setattr__(settings, "root_dir", Path(self.tmp.name))
        object.__setattr__(settings, "cloudru_api_key", "")
        object.__setattr__(settings, "cloudru_base_url", "https://foundation-models.api.cloud.ru/v1")
        object.__setattr__(settings, "cloudru_model_id", "")

    def tearDown(self) -> None:
        object.__setattr__(settings, "root_dir", self.old_root)
        object.__setattr__(settings, "cloudru_api_key", self.old_key)
        object.__setattr__(settings, "cloudru_base_url", self.old_base)
        object.__setattr__(settings, "cloudru_model_id", self.old_model)
        self.tmp.cleanup()

    def test_profile_never_returns_raw_key(self) -> None:
        raw = 'abcd-secret-"value"-wxyz'
        profile = save_cloudru_profile(
            api_key=raw,
            base_url="https://foundation-models.api.cloud.ru/v1",
            model_id="model-x",
        )
        self.assertTrue(profile["api_key_set"])
        self.assertNotIn(raw, str(profile))
        self.assertIn("abcd", profile["api_key_masked"])
        self.assertIn("wxyz", profile["api_key_masked"])

    def test_env_is_persisted_and_runtime_updates_immediately(self) -> None:
        save_cloudru_profile(
            api_key="runtime-key",
            base_url="https://foundation-models.api.cloud.ru/v1",
            model_id="model-y",
        )
        env_text = (Path(self.tmp.name) / ".env").read_text(encoding="utf-8")
        self.assertIn('CLOUDRU_API_KEY="runtime-key"', env_text)
        self.assertEqual(settings.cloudru_api_key, "runtime-key")
        self.assertEqual(settings.cloudru_model_id, "model-y")
        self.assertTrue(cloudru_profile()["configured"])

    def test_blank_key_can_preserve_existing_secret(self) -> None:
        save_cloudru_profile(
            api_key="existing",
            base_url="https://foundation-models.api.cloud.ru/v1",
            model_id="model-z",
        )
        save_cloudru_profile(
            api_key=None,
            base_url="https://foundation-models.api.cloud.ru/v1",
            model_id="model-z2",
        )
        self.assertEqual(settings.cloudru_api_key, "existing")
        self.assertEqual(settings.cloudru_model_id, "model-z2")


if __name__ == "__main__":
    unittest.main()
