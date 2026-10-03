from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

SETTINGS_PATH = settings.data_dir / "system_settings.json"
DEFAULTS = {
    "general": {
        "windows_autostart": False,
        "open_browser": True,
        "interface_language": "ru-RU",
        "theme": "system",
        "density": "normal",
        "startup_screen": "chat",
    },
    "automation": {
        "background_tasks": True,
        "worker_interval_seconds": 15,
        "auto_update": True,
        "update_interval_minutes": 15,
        "allow_portable_update": True,
        "backup_before_update": True,
    },
}


def _merge_defaults(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    result = {
        "general": {**DEFAULTS["general"], **(raw.get("general") or {})},
        "automation": {**DEFAULTS["automation"], **(raw.get("automation") or {})},
    }
    return result


def load_system_settings() -> dict:
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    return _merge_defaults(raw)


def save_system_settings(payload: dict) -> dict:
    current = load_system_settings()
    general = {**current["general"], **(payload.get("general") or {})}
    automation = {**current["automation"], **(payload.get("automation") or {})}

    if general["interface_language"] not in {"ru-RU", "en-US"}:
        raise ValueError("Недопустимый язык интерфейса.")
    if general["theme"] not in {"light", "dark", "system"}:
        raise ValueError("Недопустимая тема.")
    if general["density"] not in {"normal", "compact"}:
        raise ValueError("Недопустимая плотность интерфейса.")
    if general["startup_screen"] not in {"chat", "ai", "account", "drive", "settings"}:
        raise ValueError("Недопустимый стартовый экран.")

    automation["worker_interval_seconds"] = max(
        5, min(int(automation["worker_interval_seconds"]), 3600)
    )
    automation["update_interval_minutes"] = max(
        5, min(int(automation["update_interval_minutes"]), 1440)
    )
    for key in (
        "windows_autostart",
        "open_browser",
    ):
        general[key] = bool(general[key])
    for key in (
        "background_tasks",
        "auto_update",
        "allow_portable_update",
        "backup_before_update",
    ):
        automation[key] = bool(automation[key])

    result = {"general": general, "automation": automation}
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    set_windows_autostart(general["windows_autostart"])
    _persist_env_bridge(result)
    return result


def _env_encode(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _persist_env_bridge(payload: dict) -> None:
    env_path = settings.root_dir / ".env"
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    values = {
        "MIYORI_OPEN_BROWSER": "1" if payload["general"]["open_browser"] else "0",
        "MIYORI_AUTO_UPDATE": "1" if payload["automation"]["auto_update"] else "0",
        "MIYORI_UPDATE_INTERVAL_MINUTES": str(payload["automation"]["update_interval_minutes"]),
    }
    output: list[str] = []
    replaced: set[str] = set()
    for line in original.splitlines():
        stripped = line.strip()
        matched = False
        for key, value in values.items():
            if stripped.startswith(key + "="):
                output.append(f"{key}={_env_encode(value)}")
                replaced.add(key)
                matched = True
                break
        if not matched:
            output.append(line)
    if output and output[-1] != "":
        output.append("")
    for key, value in values.items():
        if key not in replaced:
            output.append(f"{key}={_env_encode(value)}")
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def startup_file() -> Path | None:
    if platform.system() != "Windows":
        return None
    appdata = os.getenv("APPDATA", "").strip()
    if not appdata:
        return None
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "MiyoriKitsune.cmd"
    )


def set_windows_autostart(enabled: bool) -> dict:
    target = startup_file()
    if target is None:
        return {"supported": False, "enabled": False, "path": None}
    target.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        launcher = settings.root_dir / "Miyori.bat"
        content = (
            "@echo off\r\n"
            f'cd /d "{settings.root_dir}"\r\n'
            f'start "" /min "{launcher}"\r\n'
        )
        target.write_text(content, encoding="utf-8")
    else:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
    return {
        "supported": True,
        "enabled": target.exists(),
        "path": str(target),
    }


def autostart_status() -> dict:
    target = startup_file()
    return {
        "supported": target is not None,
        "enabled": bool(target and target.exists()),
        "path": str(target) if target else None,
    }


def system_snapshot() -> dict:
    usage = shutil.disk_usage(settings.root_dir)
    install_mode = "git" if (settings.root_dir / ".git").exists() else "portable"
    db_ok = settings.database_path.exists()
    return {
        "root_dir": str(settings.root_dir),
        "data_dir": str(settings.data_dir),
        "install_mode": install_mode,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "sqlite": {
            "ok": db_ok,
            "path": str(settings.database_path),
            "size_bytes": settings.database_path.stat().st_size if db_ok else 0,
        },
        "disk": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        },
        "autostart": autostart_status(),
    }


def open_data_folder() -> None:
    path = settings.data_dir.resolve()
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def cleanup_runtime_logs() -> dict:
    removed_files = 0
    removed_bytes = 0
    for dirname in ("runtime", "logs"):
        root = settings.root_dir / dirname
        if not root.exists():
            continue
        for child in list(root.iterdir()):
            try:
                if child.is_file() or child.is_symlink():
                    try:
                        removed_bytes += child.stat().st_size
                    except OSError:
                        pass
                    child.unlink()
                    removed_files += 1
                elif child.is_dir():
                    for item in child.rglob("*"):
                        if item.is_file():
                            try:
                                removed_bytes += item.stat().st_size
                            except OSError:
                                pass
                            removed_files += 1
                    shutil.rmtree(child)
            except OSError:
                continue
    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
