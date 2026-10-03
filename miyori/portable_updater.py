from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

EXPECTED_REPO = "Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0"
PROTECTED_TOP_LEVEL = {".git", ".venv", "runtime", "data", "logs", ".env"}


class PortableUpdateError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def remote_sha(branch: str) -> str:
    url = f"https://api.github.com/repos/{EXPECTED_REPO}/commits/{branch}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Miyori-Kitsune-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PortableUpdateError(f"GitHub API HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PortableUpdateError(f"Не удалось обратиться к GitHub API: {exc}") from exc
    sha = str(data.get("sha") or "").strip()
    if len(sha) < 7:
        raise PortableUpdateError("GitHub API не вернул SHA ветки обновления.")
    return sha


def status(root: Path, state_path: Path, branch: str, fetch: bool = False) -> dict:
    saved = _read_state(state_path)
    local_sha = saved.get("installed_sha") or saved.get("to_sha")
    result = {
        "repository": EXPECTED_REPO,
        "repository_url": f"https://github.com/{EXPECTED_REPO}",
        "branch": branch,
        "install_mode": "portable",
        "git_available": bool(shutil.which("git")),
        "is_git_checkout": False,
        "origin_ok": True,
        "origin_url": f"https://github.com/{EXPECTED_REPO}",
        "current_branch": branch,
        "clean": True,
        "local_sha": local_sha,
        "remote_sha": None,
        "update_available": False,
        "ahead": 0,
        "behind": 0,
        "restart_required": bool(saved.get("restart_required")),
        "last_checked_at": saved.get("last_checked_at"),
        "last_updated_at": saved.get("last_updated_at"),
        "last_error": saved.get("last_error"),
        "backup_path": saved.get("backup_path"),
    }
    if fetch:
        try:
            sha = remote_sha(branch)
            result["remote_sha"] = sha
            result["update_available"] = not local_sha or local_sha != sha
            result["behind"] = 1 if result["update_available"] else 0
            result["last_checked_at"] = _now()
            result["last_error"] = None
        except PortableUpdateError as exc:
            result["last_checked_at"] = _now()
            result["last_error"] = str(exc)
        saved.update({
            "last_checked_at": result["last_checked_at"],
            "last_error": result["last_error"],
        })
        _write_state(state_path, saved)
    return result


def _safe_relative(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if len(path.parts) < 2:
        return None
    relative = PurePosixPath(*path.parts[1:])
    if not relative.parts:
        return None
    if relative.is_absolute() or ".." in relative.parts:
        raise PortableUpdateError("ZIP обновления содержит небезопасный путь.")
    if relative.parts[0] in PROTECTED_TOP_LEVEL:
        return None
    return relative


def _download_zip(sha: str) -> Path:
    url = f"https://codeload.github.com/{EXPECTED_REPO}/zip/{sha}"
    request = urllib.request.Request(url, headers={"User-Agent": "Miyori-Kitsune-Updater"})
    temp_dir = Path(tempfile.mkdtemp(prefix="miyori-update-"))
    target = temp_dir / "update.zip"
    try:
        with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise PortableUpdateError(f"Не удалось скачать ZIP обновления: {exc}") from exc
    return target


def apply(root: Path, state_path: Path, branch: str) -> dict:
    current = status(root, state_path, branch, fetch=True)
    if current.get("last_error"):
        raise PortableUpdateError(current["last_error"])
    sha = current.get("remote_sha")
    if not sha:
        raise PortableUpdateError("Не удалось определить GitHub SHA.")
    if not current["update_available"]:
        current["updated"] = False
        current["message"] = "Portable-проект уже актуален."
        return current

    archive_path = _download_zip(sha)
    backup_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / "data" / "update_backups" / backup_stamp
    changed = 0
    backed_up = 0

    try:
        with zipfile.ZipFile(archive_path) as archive:
            members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                relative = _safe_relative(info.filename)
                if relative is not None:
                    members.append((info, relative))

            if not members:
                raise PortableUpdateError("ZIP обновления не содержит файлов проекта.")

            for info, relative in members:
                destination = root.joinpath(*relative.parts)
                if destination.exists() and destination.is_file():
                    backup = backup_root.joinpath(*relative.parts)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, backup)
                    backed_up += 1

                destination.parent.mkdir(parents=True, exist_ok=True)
                temp_file = destination.with_name(destination.name + ".miyori-update")
                with archive.open(info) as source, temp_file.open("wb") as target:
                    shutil.copyfileobj(source, target)
                os.replace(temp_file, destination)
                changed += 1

        saved = _read_state(state_path)
        saved.update({
            "last_checked_at": _now(),
            "last_updated_at": _now(),
            "last_error": None,
            "restart_required": True,
            "installed_sha": sha,
            "to_sha": sha,
            "backup_path": str(backup_root) if backed_up else None,
            "install_mode": "portable",
        })
        _write_state(state_path, saved)
        return {
            **status(root, state_path, branch, fetch=False),
            "updated": True,
            "local_sha": sha,
            "remote_sha": sha,
            "update_available": False,
            "to_sha": sha,
            "restart_required": True,
            "files_updated": changed,
            "files_backed_up": backed_up,
            "backup_path": str(backup_root) if backed_up else None,
            "message": "Portable-обновление применено. Перезапустите Miyori.",
        }
    except (zipfile.BadZipFile, OSError) as exc:
        raise PortableUpdateError(f"Не удалось применить portable-обновление: {exc}") from exc
    finally:
        shutil.rmtree(archive_path.parent, ignore_errors=True)
