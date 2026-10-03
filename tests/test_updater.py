from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import miyori.updater as updater


@unittest.skipUnless(shutil.which("git"), "git is required")
class ProjectUpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_root = updater.ROOT
        self.old_state = updater._STATE_PATH
        updater.ROOT = self.root
        updater._STATE_PATH = self.root / "data" / "update_state.json"

        self._git("init")
        self._git("checkout", "-b", "main")
        self._git("config", "user.email", "tests@example.com")
        self._git("config", "user.name", "Miyori Tests")
        (self.root / "tracked.txt").write_text("v1\n", encoding="utf-8")
        self._git("add", "tracked.txt")
        self._git("commit", "-m", "initial")
        self._git("remote", "add", "origin", updater.EXPECTED_HTTPS)
        head = self._git("rev-parse", "HEAD")
        self._git("update-ref", "refs/remotes/origin/main", head)

    def tearDown(self) -> None:
        updater.ROOT = self.old_root
        updater._STATE_PATH = self.old_state
        self.tmp.cleanup()

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            [shutil.which("git"), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    def test_clean_expected_checkout_is_eligible(self) -> None:
        status = updater.local_status(fetch=False)
        self.assertTrue(status["origin_ok"])
        self.assertTrue(status["clean"])
        self.assertEqual(status["current_branch"], "main")
        self.assertEqual(status["ahead"], 0)
        self.assertEqual(status["behind"], 0)

    def test_dirty_tracked_file_blocks_safe_update(self) -> None:
        (self.root / "tracked.txt").write_text("local change\n", encoding="utf-8")
        status = updater.local_status(fetch=False)
        self.assertFalse(status["clean"])

    def test_untrusted_origin_is_detected(self) -> None:
        self._git("remote", "set-url", "origin", "https://github.com/example/other.git")
        status = updater.local_status(fetch=False)
        self.assertFalse(status["origin_ok"])
        self.assertIn("origin", status["last_error"])


if __name__ == "__main__":
    unittest.main()
