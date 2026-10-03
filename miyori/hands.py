from __future__ import annotations

from pathlib import Path

from .config import settings


def project_workspace(project_id: int) -> Path:
    root = settings.data_dir / "workspace" / str(project_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(project_id: int, relative_path: str) -> Path:
    root = project_workspace(project_id).resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Путь выходит за пределы рабочей папки проекта.")
    return candidate


def resolve_workspace_path(project_id: int, relative_path: str) -> Path:
    """Public safe resolver used by Tool Registry preflight/recovery checks."""
    return _safe_path(project_id, relative_path)


def list_workspace_files(project_id: int) -> dict:
    root = project_workspace(project_id)
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items.append({
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
            })
    return {"workspace": str(root), "files": items[:500]}


def read_workspace_file(project_id: int, path: str, max_chars: int = 20000) -> dict:
    target = _safe_path(project_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("Файл не найден.")
    data = target.read_text(encoding="utf-8")
    return {
        "path": path,
        "content": data[:max_chars],
        "truncated": len(data) > max_chars,
    }


def create_workspace_file(project_id: int, path: str, content: str) -> dict:
    target = _safe_path(project_id, path)
    if target.exists():
        raise ValueError("Файл уже существует. Для изменения используйте modify_workspace_file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "size_bytes": len(content.encode("utf-8")), "created": True}


def modify_workspace_file(project_id: int, path: str, content: str) -> dict:
    target = _safe_path(project_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("Файл не найден.")
    before = target.read_text(encoding="utf-8")
    target.write_text(content, encoding="utf-8")
    return {
        "path": path,
        "before_chars": len(before),
        "after_chars": len(content),
        "modified": True,
    }
