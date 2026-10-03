from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .portable_updater import PortableUpdateError, apply as apply_portable_update, status as portable_status

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_REPO = "Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0"
EXPECTED_HTTPS = f"https://github.com/{EXPECTED_REPO}.git"
EXPECTED_SSH = f"git@github.com:{EXPECTED_REPO}.git"


def _env_setting(name: str, default: str) -> str:
    direct = os.getenv(name)
    if direct is not None:
        return direct
    path = ROOT / ".env"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return default


DEFAULT_BRANCH = _env_setting("MIYORI_UPDATE_BRANCH", "main").strip() or "main"
AUTO_UPDATE = _env_setting("MIYORI_AUTO_UPDATE", "1").strip().lower() not in {"0", "false", "no", "off"}
INTERVAL_MINUTES = max(5, int(_env_setting("MIYORI_UPDATE_INTERVAL_MINUTES", "15")))
_STATE_PATH = ROOT / "data" / "update_state.json"

_monitor_lock = threading.Lock()
_monitor_running = False


class UpdateError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(*args: str, timeout: int = 25) -> str:
    git = shutil.which("git")
    if not git:
        raise UpdateError("Git не найден в PATH.")
    try:
        proc = subprocess.run(
            [git, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateError("Git-команда превысила допустимое время ожидания.") from exc
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "Git завершился с ошибкой.").strip()
        raise UpdateError(message[:1200])
    return proc.stdout.strip()


def _normalize_remote(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value[len("git@github.com:"):]
    return value.lower()


def _expected_remote() -> str:
    return f"https://github.com/{EXPECTED_REPO}".lower()


def _read_saved_state() -> dict:
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _write_saved_state(payload: dict) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def local_status(*, fetch: bool = False) -> dict:
    if not (ROOT / ".git").exists():
        result = portable_status(ROOT, _STATE_PATH, DEFAULT_BRANCH, fetch=fetch)
        result["auto_update"] = AUTO_UPDATE
        result["interval_minutes"] = INTERVAL_MINUTES
        return result

    result = {
        "repository": EXPECTED_REPO,
        "install_mode": "git",
        "repository_url": f"https://github.com/{EXPECTED_REPO}",
        "branch": DEFAULT_BRANCH,
        "auto_update": AUTO_UPDATE,
        "interval_minutes": INTERVAL_MINUTES,
        "git_available": bool(shutil.which("git")),
        "is_git_checkout": (ROOT / ".git").exists(),
        "origin_ok": False,
        "origin_url": None,
        "current_branch": None,
        "clean": False,
        "local_sha": None,
        "remote_sha": None,
        "update_available": False,
        "ahead": 0,
        "behind": 0,
        "restart_required": bool(_read_saved_state().get("restart_required")),
        "last_checked_at": _read_saved_state().get("last_checked_at"),
        "last_updated_at": _read_saved_state().get("last_updated_at"),
        "last_error": _read_saved_state().get("last_error"),
    }

    if not result["git_available"] or not result["is_git_checkout"]:
        return result

    try:
        origin = _run_git("remote", "get-url", "origin")
        branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
        local_sha = _run_git("rev-parse", "HEAD")
        dirty = _run_git("status", "--porcelain", "--untracked-files=no")

        result.update(
            {
                "origin_url": origin,
                "origin_ok": _normalize_remote(origin) == _expected_remote(),
                "current_branch": branch,
                "clean": dirty == "",
                "local_sha": local_sha,
            }
        )

        if not result["origin_ok"]:
            result["last_error"] = "origin не совпадает с доверенным репозиторием."
            return result

        if fetch:
            _run_git("fetch", "--quiet", "origin", DEFAULT_BRANCH, timeout=35)

        try:
            remote_sha = _run_git("rev-parse", f"origin/{DEFAULT_BRANCH}")
        except UpdateError:
            remote_sha = None

        result["remote_sha"] = remote_sha

        if remote_sha:
            counts = _run_git(
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...origin/{DEFAULT_BRANCH}",
            ).split()
            if len(counts) == 2:
                result["ahead"] = int(counts[0])
                result["behind"] = int(counts[1])
            result["update_available"] = result["behind"] > 0

        result["last_checked_at"] = _now()
        result["last_error"] = None
        saved = _read_saved_state()
        saved.update(
            {
                "last_checked_at": result["last_checked_at"],
                "last_error": None,
                "restart_required": result["restart_required"],
                "last_updated_at": result["last_updated_at"],
            }
        )
        _write_saved_state(saved)
        return result
    except (UpdateError, ValueError) as exc:
        result["last_checked_at"] = _now()
        result["last_error"] = str(exc)
        saved = _read_saved_state()
        saved.update(
            {
                "last_checked_at": result["last_checked_at"],
                "last_error": result["last_error"],
            }
        )
        _write_saved_state(saved)
        return result


def apply_update() -> dict:
    if not (ROOT / ".git").exists():
        try:
            result = apply_portable_update(ROOT, _STATE_PATH, DEFAULT_BRANCH)
            result["auto_update"] = AUTO_UPDATE
            result["interval_minutes"] = INTERVAL_MINUTES
            return result
        except PortableUpdateError as exc:
            raise UpdateError(str(exc)) from exc

    status = local_status(fetch=True)

    if not status["git_available"]:
        raise UpdateError("Git не установлен.")
    if not status["origin_ok"]:
        raise UpdateError("origin не совпадает с доверенным репозиторием Miyori.")
    if status["current_branch"] != DEFAULT_BRANCH:
        raise UpdateError(f"Автообновление разрешено только из ветки {DEFAULT_BRANCH}.")
    if not status["clean"]:
        raise UpdateError("Есть локальные изменения. Автообновление остановлено, чтобы не потерять файлы.")
    if status["ahead"] > 0:
        raise UpdateError("Локальная ветка содержит собственные коммиты. Автообновление остановлено.")
    if not status["update_available"]:
        status["updated"] = False
        status["message"] = "Локальный проект уже актуален."
        return status

    before = status["local_sha"]
    _run_git("merge", "--ff-only", f"origin/{DEFAULT_BRANCH}", timeout=40)
    after = _run_git("rev-parse", "HEAD")

    saved = _read_saved_state()
    saved.update(
        {
            "last_checked_at": _now(),
            "last_updated_at": _now(),
            "last_error": None,
            "restart_required": True,
            "from_sha": before,
            "to_sha": after,
        }
    )
    _write_saved_state(saved)

    result = local_status(fetch=False)
    result.update(
        {
            "updated": True,
            "from_sha": before,
            "to_sha": after,
            "restart_required": True,
            "message": "Обновление применено. Перезапустите Miyori, чтобы новый код вступил в силу.",
        }
    )
    return result


def clear_restart_required() -> None:
    saved = _read_saved_state()
    if saved.get("restart_required"):
        saved["restart_required"] = False
        _write_saved_state(saved)


def _monitor_loop() -> None:
    global _monitor_running
    try:
        while True:
            try:
                status = local_status(fetch=True)
                if AUTO_UPDATE and status.get("update_available"):
                    if status.get("install_mode") == "portable" or (
                        status.get("clean")
                        and status.get("origin_ok")
                        and status.get("current_branch") == DEFAULT_BRANCH
                        and status.get("ahead", 0) == 0
                    ):
                        apply_update()
            except Exception as exc:
                saved = _read_saved_state()
                saved.update({"last_checked_at": _now(), "last_error": str(exc)})
                _write_saved_state(saved)
            time.sleep(INTERVAL_MINUTES * 60)
    finally:
        with _monitor_lock:
            _monitor_running = False


def start_update_monitor() -> None:
    global _monitor_running
    if not AUTO_UPDATE:
        return
    with _monitor_lock:
        if _monitor_running:
            return
        _monitor_running = True
    thread = threading.Thread(
        target=_monitor_loop,
        daemon=True,
        name="miyori-auto-updater",
    )
    thread.start()


def cli_auto_update() -> int:
    if not AUTO_UPDATE:
        print("[update] Auto-update disabled.")
        return 0
    try:
        result = apply_update()
        if result.get("updated"):
            print(
                "[update] Обновление применено до запуска сервера. "
                "Текущий запуск Miyori уже продолжится на новой версии."
            )
        else:
            print("[update] " + result.get("message", "Локальный проект уже актуален."))
        return 0
    except UpdateError as exc:
        print(f"[update] skipped: {exc}")
        return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Apply safe fast-forward update if available.")
    parser.add_argument("--status", action="store_true", help="Print update status.")
    args = parser.parse_args()

    if args.auto:
        raise SystemExit(cli_auto_update())

    status = local_status(fetch=args.status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
