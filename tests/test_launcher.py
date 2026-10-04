from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from miyori import launcher


ROOT = Path(__file__).resolve().parent.parent


class LauncherUnitTests(unittest.TestCase):
    def test_python_minimum_is_explicit(self) -> None:
        self.assertTrue(launcher.python_supported((3, 10, 0)))
        self.assertTrue(launcher.python_supported((3, 12, 0)))
        self.assertFalse(launcher.python_supported((3, 9, 99)))

    def test_browser_host_normalizes_bind_all_addresses(self) -> None:
        self.assertEqual(launcher.browser_host("0.0.0.0"), "127.0.0.1")
        self.assertEqual(launcher.browser_host("::"), "127.0.0.1")
        self.assertEqual(launcher.browser_host("127.0.0.1"), "127.0.0.1")

    def test_preflight_rejects_busy_non_miyori_port(self) -> None:
        with patch("miyori.launcher._read_health", return_value=None), patch(
            "miyori.launcher.port_is_open",
            return_value=True,
        ):
            ok, message = launcher.run_preflight("127.0.0.1", 8765)
        self.assertFalse(ok)
        self.assertIn("уже занят", message)

    def test_preflight_accepts_existing_miyori_server(self) -> None:
        with patch(
            "miyori.launcher._read_health",
            return_value={"name": "Miyori Kitsune AI", "version": "00.00.test"},
        ):
            ok, message = launcher.run_preflight("127.0.0.1", 8765)
        self.assertTrue(ok)
        self.assertIn("уже запущена", message)

    def test_runtime_files_exist_in_repository(self) -> None:
        self.assertEqual(launcher.ensure_runtime_files(), [])


class WindowsBatchContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.batch = (ROOT / "Miyori.bat").read_text(
            encoding="utf-8",
            errors="replace",
        )

    def test_batch_uses_real_launcher_instead_of_executing_app_module(self) -> None:
        self.assertIn('-m miyori.launcher', self.batch)
        self.assertNotIn('"%RUN_PYTHON%" app.py', self.batch)

    def test_batch_checks_supported_python(self) -> None:
        self.assertIn("sys.version_info >= (3,10)", self.batch)
        self.assertIn("setup-portable.ps1", self.batch)

    def test_batch_has_ci_preflight_mode_and_failure_diagnostics(self) -> None:
        self.assertIn('"--check"', self.batch)
        self.assertIn("logs\\last-startup.log", self.batch)
        self.assertIn("if defined CI exit /b 1", self.batch)

    def test_batch_forces_utf8_python_stdio(self) -> None:
        self.assertIn('set "PYTHONUTF8=1"', self.batch)
        self.assertIn('set "PYTHONIOENCODING=utf-8"', self.batch)


if __name__ == "__main__":
    unittest.main()
