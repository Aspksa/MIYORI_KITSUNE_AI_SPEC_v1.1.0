from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect, utc_now
from .persona import load_persona_corpus


MIYORI_APPEARANCE_SCHEMA_VERSION = "1.0.0"
PORTRAIT_MAX_BYTES = 5 * 1024 * 1024
PORTRAIT_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
_APPEARANCE_FIELDS = {
    "hair_color": "Цвет волос",
    "eye_color": "Цвет глаз",
    "tail_count": "Точное число хвостов",
    "main_outfit": "Основной наряд",
}


def init_appearance_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS miyori_appearance_profile (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                hair_color TEXT,
                eye_color TEXT,
                tail_count INTEGER,
                main_outfit TEXT,
                portrait_path TEXT,
                portrait_mime TEXT,
                portrait_sha256 TEXT,
                portrait_size_bytes INTEGER,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO miyori_appearance_profile(id, revision, updated_at)
            VALUES (1, 0, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (utc_now(),),
        )


def _clean_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    clean = " ".join(str(value).strip().split())
    if not clean:
        return None
    if len(clean) > max_length:
        raise ValueError(f"Значение слишком длинное; максимум {max_length} символов.")
    return clean


def _appearance_choice_labels() -> list[str]:
    corpus = load_persona_corpus()
    identity = corpus.get("identity") or {}
    values = [
        str(value)
        for value in (identity.get("appearance_open_for_user_choice") or [])
        if str(value).strip()
    ]
    return values


def _valid_image_signature(data: bytes, mime_type: str) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _portrait_dir() -> Path:
    path = settings.data_dir / "appearance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _portrait_path_from_row(row: dict[str, Any]) -> Path | None:
    raw = str(row.get("portrait_path") or "").strip()
    if not raw:
        return None
    path = (settings.data_dir / raw).resolve()
    root = settings.data_dir.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _state(selection: dict[str, Any]) -> tuple[str, int]:
    selected = sum(
        1
        for value in selection.values()
        if value is not None and value != ""
    )
    if selected == 0:
        return "appearance_unconfigured", selected
    if selected < len(_APPEARANCE_FIELDS):
        return "appearance_partial", selected
    return "appearance_configured", selected


def get_appearance_profile() -> dict:
    init_appearance_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, hair_color, eye_color, tail_count, main_outfit,
                   portrait_path, portrait_mime, portrait_sha256,
                   portrait_size_bytes, revision, updated_at
            FROM miyori_appearance_profile
            WHERE id = 1
            """
        ).fetchone()
    item = dict(row) if row else {}
    selection = {
        "hair_color": item.get("hair_color"),
        "eye_color": item.get("eye_color"),
        "tail_count": (
            int(item["tail_count"])
            if item.get("tail_count") is not None
            else None
        ),
        "main_outfit": item.get("main_outfit"),
    }
    state, selected = _state(selection)
    path = _portrait_path_from_row(item)
    asset_exists = bool(path and path.is_file())

    return {
        "schema_version": MIYORI_APPEARANCE_SCHEMA_VERSION,
        "state": state,
        "selection": selection,
        "completion": {
            "selected": selected,
            "total": len(_APPEARANCE_FIELDS),
            "complete": selected == len(_APPEARANCE_FIELDS),
        },
        "fields": [
            {
                "key": key,
                "label": label,
                "owner_choice": True,
                "selected": selection[key] is not None,
            }
            for key, label in _APPEARANCE_FIELDS.items()
        ],
        "persona_open_choices": _appearance_choice_labels(),
        "asset": {
            "kind": "static_portrait" if asset_exists else None,
            "url": "/api/miyori/appearance/portrait" if asset_exists else None,
            "mime": item.get("portrait_mime") if asset_exists else None,
            "sha256": item.get("portrait_sha256") if asset_exists else None,
            "size_bytes": int(item.get("portrait_size_bytes") or 0) if asset_exists else 0,
            "supports_dynamic_pose": False,
            "supports_expression": False,
        },
        "policy": {
            "system_defaults_allowed": False,
            "model_may_choose_owner_fields": False,
            "partial_configuration_allowed": True,
            "asset_changes_persona_identity": False,
            "static_portrait_may_claim_dynamic_pose": False,
        },
        "revision": int(item.get("revision") or 0),
        "updated_at": item.get("updated_at"),
    }


def update_appearance_profile(
    *,
    hair_color: str | None,
    eye_color: str | None,
    tail_count: int | None,
    main_outfit: str | None,
) -> dict:
    hair = _clean_text(hair_color, 80)
    eyes = _clean_text(eye_color, 80)
    outfit = _clean_text(main_outfit, 500)
    tails = None if tail_count is None else int(tail_count)
    if tails is not None and tails < 1:
        raise ValueError("Точное число хвостов должно быть положительным.")

    init_appearance_db()
    with connect() as conn:
        conn.execute(
            """
            UPDATE miyori_appearance_profile
            SET hair_color = ?, eye_color = ?, tail_count = ?, main_outfit = ?,
                revision = revision + 1, updated_at = ?
            WHERE id = 1
            """,
            (hair, eyes, tails, outfit, utc_now()),
        )
    return get_appearance_profile()


def save_portrait_asset(data: bytes, mime_type: str) -> dict:
    if mime_type not in PORTRAIT_MIME_TYPES:
        raise ValueError("Портрет должен быть PNG, JPEG или WEBP.")
    if not data:
        raise ValueError("Файл портрета пуст.")
    if not _valid_image_signature(data, mime_type):
        raise ValueError("Содержимое файла не соответствует заявленному формату изображения.")
    if len(data) > PORTRAIT_MAX_BYTES:
        raise ValueError("Портрет слишком большой. Максимум 5 МБ.")

    init_appearance_db()
    directory = _portrait_dir()
    for old in directory.glob("miyori-portrait.*"):
        try:
            old.unlink()
        except OSError:
            pass

    suffix = PORTRAIT_MIME_TYPES[mime_type]
    target = directory / f"miyori-portrait{suffix}"
    target.write_bytes(data)
    relative = str(target.relative_to(settings.data_dir))
    digest = hashlib.sha256(data).hexdigest()

    with connect() as conn:
        conn.execute(
            """
            UPDATE miyori_appearance_profile
            SET portrait_path = ?, portrait_mime = ?, portrait_sha256 = ?,
                portrait_size_bytes = ?, revision = revision + 1, updated_at = ?
            WHERE id = 1
            """,
            (relative, mime_type, digest, len(data), utc_now()),
        )
    return get_appearance_profile()


def remove_portrait_asset() -> dict:
    init_appearance_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT portrait_path FROM miyori_appearance_profile WHERE id = 1"
        ).fetchone()
    item = dict(row) if row else {}
    path = _portrait_path_from_row(item)
    if path:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    with connect() as conn:
        conn.execute(
            """
            UPDATE miyori_appearance_profile
            SET portrait_path = NULL, portrait_mime = NULL,
                portrait_sha256 = NULL, portrait_size_bytes = NULL,
                revision = revision + 1, updated_at = ?
            WHERE id = 1
            """,
            (utc_now(),),
        )
    return get_appearance_profile()


def portrait_asset_path() -> Path | None:
    profile = get_appearance_profile()
    if not profile["asset"]["url"]:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT portrait_path FROM miyori_appearance_profile WHERE id = 1"
        ).fetchone()
    item = dict(row) if row else {}
    path = _portrait_path_from_row(item)
    return path if path and path.is_file() else None
