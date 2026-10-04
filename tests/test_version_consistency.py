from __future__ import annotations

import re
import unittest
from pathlib import Path

from miyori import __version__
from miyori.module_registry import PROJECT_VERSION


ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_runtime_and_published_assets_share_project_version(self) -> None:
        self.assertEqual(__version__, PROJECT_VERSION)

        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn(f'version="{PROJECT_VERSION}"', app_text)
        self.assertIn(f'"version": "{PROJECT_VERSION}"', app_text)
        self.assertIn(f'"project_version": "{PROJECT_VERSION}"', app_text)

        script_versions = re.findall(
            r'/static/js/[^"?]+\.js\?v=([0-9.]+)',
            template,
        )
        self.assertTrue(script_versions)
        self.assertEqual(set(script_versions), {PROJECT_VERSION})


if __name__ == "__main__":
    unittest.main()
