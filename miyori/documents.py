from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import settings

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".json"}
MAX_FILE_BYTES = 5 * 1024 * 1024
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 180


def project_document_dir(project_id: int) -> Path:
    path = settings.data_dir / "documents" / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document.txt"
    return re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9._ -]+", "_", name)


def decode_document(filename: str, data: bytes) -> str:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Файл слишком большой. Текущий лимит — 5 МБ.")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Формат пока не поддерживается. Разрешены: {allowed}")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Документ должен быть в UTF-8.") from exc

    if suffix == ".json":
        try:
            obj = json.loads(text)
            text = json.dumps(obj, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON-файл содержит синтаксическую ошибку.") from exc

    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_text(text: str) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    length = len(clean)

    while start < length:
        end = min(length, start + CHUNK_SIZE)
        if end < length:
            split = max(
                clean.rfind("\n\n", start, end),
                clean.rfind(". ", start, end),
                clean.rfind("\n", start, end),
            )
            if split > start + CHUNK_SIZE // 2:
                end = split + 1

        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


def save_original(project_id: int, filename: str, data: bytes, digest: str) -> str:
    safe = safe_filename(filename)
    target = project_document_dir(project_id) / f"{digest[:12]}_{safe}"
    if not target.exists():
        target.write_bytes(data)
    return str(target.relative_to(settings.data_dir))
