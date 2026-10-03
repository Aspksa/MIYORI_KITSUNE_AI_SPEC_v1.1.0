from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from docx import Document as WordDocument
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

from .config import settings

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json",
    ".pdf", ".docx", ".xlsx", ".pptx",
}
MAX_FILE_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 180

DRIVE_DIR_NAME = "Документы - Облако - Miyori"
FILES_DIR_NAME = "Файлы"
TRASH_DIR_NAME = "Корзина"

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def project_drive_dir(project_id: int) -> Path:
    """Физическое хранилище Miyori Drive внутри рабочей папки проекта."""
    path = settings.data_dir / "workspace" / str(project_id) / DRIVE_DIR_NAME
    (path / FILES_DIR_NAME).mkdir(parents=True, exist_ok=True)
    (path / TRASH_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return path


def project_document_dir(project_id: int) -> Path:
    """Совместимое имя для корня активных файлов проекта."""
    return project_drive_dir(project_id) / FILES_DIR_NAME


def drive_relative_root(project_id: int) -> str:
    return str(project_drive_dir(project_id).relative_to(settings.data_dir)).replace("\\", "/")


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document.txt"
    clean = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9._ ()\-]+", "_", name).rstrip(" .")
    return clean or "document.txt"


def safe_folder_name(name: str) -> str:
    clean = " ".join(str(name or "").strip().split())
    if not clean:
        raise ValueError("Название папки пустое.")
    if len(clean) > 120:
        raise ValueError("Название папки слишком длинное.")
    if re.search(r'[<>:"/\\|?*]', clean):
        raise ValueError('В названии папки нельзя использовать символы < > : " / \\ | ? *.')
    if clean.endswith((".", " ")):
        raise ValueError("Название папки не может заканчиваться точкой или пробелом.")
    stem = clean.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        raise ValueError("Это имя зарезервировано Windows.")
    return clean


def _data_relative(path: Path) -> str:
    root = settings.data_dir.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Путь выходит за пределы каталога данных Miyori.")
    return str(resolved.relative_to(root)).replace("\\", "/")


def resolve_data_path(relative_path: str) -> Path:
    root = settings.data_dir.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Путь выходит за пределы каталога данных Miyori.")
    return candidate


def ensure_drive_folder(project_id: int, folder_parts: list[str] | tuple[str, ...] | None = None) -> Path:
    target = project_document_dir(project_id)
    for part in folder_parts or []:
        target = target / safe_folder_name(part)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _unique_file_target(directory: Path, filename: str, digest: str | None = None) -> Path:
    safe = safe_filename(filename)
    target = directory / safe
    if not target.exists():
        return target

    stem = Path(safe).stem
    suffix = Path(safe).suffix
    token = (digest or "")[:8]
    if token:
        candidate = directory / f"{stem} ({token}){suffix}"
        if not candidate.exists():
            return candidate

    index = 2
    while True:
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _unique_dir_target(directory: Path, name: str) -> Path:
    safe = safe_folder_name(name)
    target = directory / safe
    if not target.exists():
        return target
    index = 2
    while True:
        candidate = directory / f"{safe} ({index})"
        if not candidate.exists():
            return candidate
        index += 1


def _decode_text(filename: str, data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Текстовый документ должен быть в UTF-8.") from exc

    if Path(filename).suffix.lower() == ".json":
        try:
            obj = json.loads(text)
            text = json.dumps(obj, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON-файл содержит синтаксическую ошибку.") from exc
    return text


def _decode_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("Не удалось открыть PDF.") from exc

    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append(f"[PDF · страница {index}]\n{text}")

    if not pages:
        raise ValueError(
            "В PDF не найден извлекаемый текст. "
            "Сканированные PDF пока требуют отдельного OCR."
        )
    return "\n\n".join(pages)


def _decode_docx(data: bytes) -> str:
    try:
        document = WordDocument(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("Не удалось открыть DOCX.") from exc

    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table_index, table in enumerate(document.tables, start=1):
        rows: list[str] = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            parts.append(f"[DOCX · таблица {table_index}]\n" + "\n".join(rows))

    if not parts:
        raise ValueError("В DOCX не найден текст.")
    return "\n\n".join(parts)


def _decode_xlsx(data: bytes) -> str:
    try:
        workbook = load_workbook(
            io.BytesIO(data),
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise ValueError("Не удалось открыть XLSX.") from exc

    parts: list[str] = []
    try:
        for sheet in workbook.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    rows.append(" | ".join(values))
            if rows:
                parts.append(f"[XLSX · лист {sheet.title}]\n" + "\n".join(rows))
    finally:
        workbook.close()

    if not parts:
        raise ValueError("В XLSX не найдено данных.")
    return "\n\n".join(parts)


def _decode_pptx(data: bytes) -> str:
    try:
        presentation = Presentation(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("Не удалось открыть PPTX.") from exc

    parts: list[str] = []
    for slide_index, slide in enumerate(presentation.slides, start=1):
        slide_parts: list[str] = []
        for shape in slide.shapes:
            text = getattr(shape, "text", "")
            if text and text.strip():
                slide_parts.append(text.strip())

            if getattr(shape, "has_table", False):
                table_rows: list[str] = []
                for row in shape.table.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(cells):
                        table_rows.append(" | ".join(cells))
                if table_rows:
                    slide_parts.append("\n".join(table_rows))

        if slide_parts:
            parts.append(
                f"[PPTX · слайд {slide_index}]\n" +
                "\n".join(slide_parts)
            )

    if not parts:
        raise ValueError("В PPTX не найден текст.")
    return "\n\n".join(parts)


def decode_document(filename: str, data: bytes) -> str:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Файл слишком большой. Текущий лимит — 25 МБ.")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Формат пока не поддерживается. Разрешены: {allowed}. "
            "Старые .doc/.xls/.ppt требуют предварительного сохранения "
            "в .docx/.xlsx/.pptx."
        )

    if suffix in {".txt", ".md", ".markdown", ".json"}:
        text = _decode_text(filename, data)
    elif suffix == ".pdf":
        text = _decode_pdf(data)
    elif suffix == ".docx":
        text = _decode_docx(data)
    elif suffix == ".xlsx":
        text = _decode_xlsx(data)
    elif suffix == ".pptx":
        text = _decode_pptx(data)
    else:
        raise ValueError("Неподдерживаемый формат документа.")

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


def save_original(
    project_id: int,
    filename: str,
    data: bytes,
    digest: str,
    folder_parts: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Сохраняет байт-в-байт оригинал в активном дереве Miyori Drive."""
    directory = ensure_drive_folder(project_id, folder_parts)
    target = _unique_file_target(directory, filename, digest)
    target.write_bytes(data)
    return _data_relative(target)


def move_active_document(
    project_id: int,
    stored_path: str,
    filename: str,
    folder_parts: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Move an active original inside the same project Drive tree."""
    source = resolve_data_path(stored_path)
    if not source.exists() or not source.is_file():
        raise ValueError("Оригинал документа не найден на диске.")

    active_root = project_document_dir(project_id).resolve()
    resolved_source = source.resolve()
    if resolved_source != active_root and active_root not in resolved_source.parents:
        raise ValueError("Документ находится вне активного хранилища проекта.")

    directory = ensure_drive_folder(project_id, folder_parts)
    if source.parent.resolve() == directory.resolve():
        return _data_relative(source)

    target = _unique_file_target(directory, filename)
    shutil.move(str(source), str(target))
    return _data_relative(target)


def move_document_to_trash(
    project_id: int,
    stored_path: str,
    filename: str,
    document_id: int,
) -> str:
    source = resolve_data_path(stored_path)
    if not source.exists() or not source.is_file():
        raise ValueError("Оригинал документа не найден на диске.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trash = project_drive_dir(project_id) / TRASH_DIR_NAME
    target = _unique_file_target(
        trash,
        f"{stamp}_doc-{document_id}_{safe_filename(filename)}",
    )
    shutil.move(str(source), str(target))
    return _data_relative(target)


def restore_document_from_trash(
    project_id: int,
    trash_path: str,
    filename: str,
    folder_parts: list[str] | tuple[str, ...] | None = None,
) -> str:
    source = resolve_data_path(trash_path)
    if not source.exists() or not source.is_file():
        raise ValueError("Оригинал документа не найден в корзине.")

    directory = ensure_drive_folder(project_id, folder_parts)
    target = _unique_file_target(directory, filename)
    shutil.move(str(source), str(target))
    return _data_relative(target)


def move_folder_to_trash(
    project_id: int,
    folder_parts: list[str] | tuple[str, ...],
    folder_id: int,
) -> str:
    parts = [safe_folder_name(part) for part in folder_parts]
    if not parts:
        raise ValueError("Нельзя удалить корень Miyori Drive.")

    source = project_document_dir(project_id).joinpath(*parts)
    if not source.exists() or not source.is_dir():
        raise ValueError("Папка не найдена на диске.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trash = project_drive_dir(project_id) / TRASH_DIR_NAME
    target = _unique_dir_target(trash, f"{stamp}_folder-{folder_id}_{parts[-1]}")
    shutil.move(str(source), str(target))
    return _data_relative(target)


def restore_folder_from_trash(
    project_id: int,
    trash_path: str,
    parent_parts: list[str] | tuple[str, ...],
    folder_name: str,
) -> tuple[str, str]:
    source = resolve_data_path(trash_path)
    if not source.exists() or not source.is_dir():
        raise ValueError("Папка не найдена в корзине.")

    parent = ensure_drive_folder(project_id, parent_parts)
    target = parent / safe_folder_name(folder_name)
    if target.exists():
        raise ValueError(
            "Исходное место папки уже занято. Освободите его перед восстановлением."
        )
    shutil.move(str(source), str(target))
    return _data_relative(target), target.name


def migrate_legacy_document(
    project_id: int,
    stored_path: str,
    filename: str,
    digest: str,
    folder_parts: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Копирует старый оригинал в Miyori Drive без удаления исходной копии."""
    source = resolve_data_path(stored_path)
    active_root = project_document_dir(project_id).resolve()
    try:
        resolved = source.resolve()
        if resolved == active_root or active_root in resolved.parents:
            return _data_relative(resolved)
    except OSError:
        pass

    if not source.exists() or not source.is_file():
        return stored_path

    data = source.read_bytes()
    if sha256_bytes(data) != digest:
        raise ValueError(f"Контрольная сумма оригинала «{filename}» не совпадает.")
    return save_original(project_id, filename, data, digest, folder_parts)
