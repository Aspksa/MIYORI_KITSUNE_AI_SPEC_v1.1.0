from __future__ import annotations

import hashlib
import io
import json
import re
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


def project_document_dir(project_id: int) -> Path:
    path = settings.data_dir / "documents" / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document.txt"
    return re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9._ -]+", "_", name)


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


def save_original(project_id: int, filename: str, data: bytes, digest: str) -> str:
    safe = safe_filename(filename)
    target = project_document_dir(project_id) / f"{digest[:12]}_{safe}"
    if not target.exists():
        target.write_bytes(data)
    return str(target.relative_to(settings.data_dir))
