from __future__ import annotations

import base64
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import fitz
import httpx
from PIL import Image, ImageOps

from .account import list_cloudru_models
from .config import settings
from .db import connect, get_document, is_task_cancel_requested, replace_document_chunks, utc_now
from .document_intelligence import build_local_document_intelligence
from .documents import (
    DocumentBlock,
    StructuredDocument,
    chunk_text,
    extract_structured_document,
    resolve_data_path,
)

PREFERRED_OCR_MODEL = "deepseek-ai/DeepSeek-OCR-2"
PREFERRED_VISION_MODEL = "moonshotai/Kimi-K2.6"
MAX_VISUAL_ITEMS = 24
MAX_RENDER_EDGE = 1800
MAX_IMAGE_BYTES = 7 * 1024 * 1024
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA_PREFIXES = {
    ".docx": "word/media/",
    ".pptx": "ppt/media/",
    ".xlsx": "xl/media/",
}


@dataclass
class VisualItem:
    locator: str
    kind: str
    image: bytes
    page_number: int | None = None
    title: str | None = None


def init_document_vision_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_visual_state(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                requested_items INTEGER NOT NULL DEFAULT 0,
                processed_items INTEGER NOT NULL DEFAULT 0,
                failed_items INTEGER NOT NULL DEFAULT 0,
                ocr_model_id TEXT,
                vision_model_id TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id,document_id)
            );
            CREATE TABLE IF NOT EXISTS document_visual_extractions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                locator TEXT NOT NULL,
                page_number INTEGER,
                source_kind TEXT NOT NULL,
                ocr_text TEXT NOT NULL DEFAULT '',
                visual_summary TEXT NOT NULL DEFAULT '',
                visual_elements_json TEXT NOT NULL DEFAULT '[]',
                ocr_model_id TEXT,
                vision_model_id TEXT,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(document_id,locator)
            );
            CREATE INDEX IF NOT EXISTS idx_document_visual_project
              ON document_visual_extractions(project_id,document_id);
            """
        )


def _set_state(
    project_id: int,
    document_id: int,
    status: str,
    *,
    requested: int | None = None,
    processed: int | None = None,
    failed: int | None = None,
    ocr_model: str | None = None,
    vision_model: str | None = None,
    error: str | None = None,
) -> None:
    init_document_vision_db()
    now = utc_now()
    with connect() as db:
        current = db.execute(
            "SELECT requested_items,processed_items,failed_items FROM document_visual_state "
            "WHERE project_id=? AND document_id=?",
            (project_id, document_id),
        ).fetchone()
        req = int(requested if requested is not None else (current["requested_items"] if current else 0))
        done = int(processed if processed is not None else (current["processed_items"] if current else 0))
        bad = int(failed if failed is not None else (current["failed_items"] if current else 0))
        db.execute(
            """
            INSERT INTO document_visual_state(
              project_id,document_id,status,requested_items,processed_items,
              failed_items,ocr_model_id,vision_model_id,last_error,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(project_id,document_id) DO UPDATE SET
              status=excluded.status,
              requested_items=excluded.requested_items,
              processed_items=excluded.processed_items,
              failed_items=excluded.failed_items,
              ocr_model_id=COALESCE(excluded.ocr_model_id,document_visual_state.ocr_model_id),
              vision_model_id=COALESCE(excluded.vision_model_id,document_visual_state.vision_model_id),
              last_error=excluded.last_error,
              updated_at=excluded.updated_at
            """,
            (project_id, document_id, status, req, done, bad,
             ocr_model, vision_model, error, now, now),
        )


def mark_document_vision_queued(
    project_id: int,
    document_id: int,
) -> dict:
    if not get_document(project_id, document_id):
        raise LookupError("Документ не найден в текущем проекте.")
    _set_state(
        project_id,
        document_id,
        "queued",
        error=None,
    )
    return document_vision_status(project_id, document_id)


def document_vision_status(project_id: int, document_id: int) -> dict:
    init_document_vision_db()
    if not get_document(project_id, document_id):
        raise LookupError("Документ не найден в текущем проекте.")
    with connect() as db:
        state = db.execute(
            """
            SELECT project_id,document_id,status,requested_items,processed_items,
                   failed_items,ocr_model_id,vision_model_id,last_error,updated_at
            FROM document_visual_state WHERE project_id=? AND document_id=?
            """,
            (project_id, document_id),
        ).fetchone()
        rows = db.execute(
            """
            SELECT locator,page_number,source_kind,status,ocr_model_id,vision_model_id,
                   length(ocr_text) AS text_chars,
                   length(visual_summary) AS visual_chars,error,updated_at
            FROM document_visual_extractions
            WHERE project_id=? AND document_id=?
            ORDER BY COALESCE(page_number,999999),locator
            """,
            (project_id, document_id),
        ).fetchall()
    return {
        "state": dict(state) if state else {
            "project_id": project_id,
            "document_id": document_id,
            "status": "not_started",
            "requested_items": 0,
            "processed_items": 0,
            "failed_items": 0,
            "ocr_model_id": None,
            "vision_model_id": None,
            "last_error": None,
        },
        "items": [dict(row) for row in rows],
        "bbox_verified": False,
        "provenance_note": (
            "Источник фиксируется до страницы или встроенного media-объекта. "
            "Координаты области не заявляются без проверяемой системы координат."
        ),
    }


def _normalize_image(data: bytes) -> bytes:
    if len(data) > MAX_IMAGE_BYTES * 4:
        raise ValueError("Изображение слишком большое для визуального анализа.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((MAX_RENDER_EDGE, MAX_RENDER_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            result = output.getvalue()
    except Exception as exc:
        raise ValueError("Не удалось декодировать изображение.") from exc
    if len(result) > MAX_IMAGE_BYTES:
        with Image.open(io.BytesIO(result)) as image:
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            result = output.getvalue()
    return result


def _pdf_items(data: bytes, include_text_pages: bool) -> tuple[list[VisualItem], int]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Не удалось открыть PDF для OCR.") from exc
    result: list[VisualItem] = []
    try:
        total = int(doc.page_count)
        for index in range(total):
            page = doc.load_page(index)
            native = (page.get_text("text") or "").strip()
            if native and not include_text_pages:
                continue
            longest = max(float(page.rect.width), float(page.rect.height), 1.0)
            scale = max(0.75, min(2.0, MAX_RENDER_EDGE / longest))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            result.append(
                VisualItem(
                    locator=f"pdf:page:{index + 1}",
                    kind="pdf_page",
                    image=_normalize_image(pix.tobytes("png")),
                    page_number=index + 1,
                    title=f"Страница {index + 1}",
                )
            )
    finally:
        doc.close()
    return result, total


def _archive_media_items(filename: str, data: bytes) -> list[VisualItem]:
    suffix = Path(filename).suffix.lower()
    prefix = MEDIA_PREFIXES.get(suffix)
    if not prefix:
        return []
    result: list[VisualItem] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = sorted(
                name for name in archive.namelist()
                if name.startswith(prefix) and Path(name).suffix.lower() in IMAGE_SUFFIXES
            )
            for name in names:
                try:
                    normalized = _normalize_image(archive.read(name))
                except (KeyError, ValueError):
                    continue
                result.append(
                    VisualItem(
                        locator=f"{suffix.lstrip('.')}:media:{name[len(prefix):]}",
                        kind=f"{suffix.lstrip('.')}_media",
                        image=normalized,
                        title=Path(name).name,
                    )
                )
    except (zipfile.BadZipFile, OSError):
        return []
    return result


def _visual_items(
    filename: str,
    data: bytes,
    *,
    include_text_pages: bool,
) -> tuple[list[VisualItem], int]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _pdf_items(data, include_text_pages)
    if suffix in IMAGE_SUFFIXES:
        return [
            VisualItem(
                locator="image:page:1",
                kind="image",
                image=_normalize_image(data),
                page_number=1,
                title=Path(filename).name,
            )
        ], 1
    return _archive_media_items(filename, data), 0


async def _resolve_models() -> tuple[str, str | None]:
    catalog = await list_cloudru_models()
    if not catalog.get("ok"):
        raise ValueError("Cloud.ru не настроен: OCR требует рабочий API-ключ.")
    models = catalog.get("models") or []
    ids = {str(item.get("id")) for item in models}
    ocr = PREFERRED_OCR_MODEL if PREFERRED_OCR_MODEL in ids else None
    if not ocr:
        ocr = next(
            (
                str(item["id"])
                for item in models
                if "ocr" in str(item.get("type") or "").lower()
                or "ocr" in str(item.get("id") or "").lower()
            ),
            None,
        )
    if not ocr:
        raise ValueError("В текущем аккаунте Cloud.ru не найдена OCR-модель.")
    vision = PREFERRED_VISION_MODEL if PREFERRED_VISION_MODEL in ids else None
    return ocr, vision


def _data_url(image: bytes) -> str:
    png_signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    mime = "image/png" if image.startswith(png_signature) else "image/jpeg"
    return "data:" + mime + ";base64," + base64.b64encode(image).decode("ascii")


def _json_or_text(value: str) -> dict:
    raw = str(value or "").strip()
    fence = chr(96) * 3
    if raw.startswith(fence):
        raw = raw.strip(chr(96))
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    candidates = [raw]
    left = raw.find("{")
    right = raw.rfind("}")
    if 0 <= left < right:
        candidates.append(raw[left:right + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {"text": str(value or "").strip()}


async def _image_completion(model: str, image: bytes, prompt: str) -> str:
    if not settings.cloudru_api_key:
        raise ValueError("Cloud.ru API-ключ не настроен.")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _data_url(image)}},
            ],
        }],
        "temperature": 0,
        "max_completion_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {settings.cloudru_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.cloudru_base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.is_error:
        detail = response.text[:1000]
        raise ValueError(
            f"Cloud.ru vision/OCR вернул HTTP {response.status_code}: "
            f"{detail or 'без текста ошибки'}"
        )
    data = response.json()
    try:
        return str(data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Cloud.ru вернул неожиданный OCR-ответ.") from exc


async def _analyze_item(
    item: VisualItem,
    *,
    ocr_model: str,
    vision_model: str | None,
) -> dict:
    ocr_raw = await _image_completion(
        ocr_model,
        item.image,
        (
            "Распознай весь читаемый текст. Не додумывай символы. "
            "Сохрани строки, заголовки и табличные строки насколько возможно. "
            'Верни JSON {"text":"..."}. '
            "Если текста нет, верни пустую строку."
        ),
    )
    parsed = _json_or_text(ocr_raw)
    text = str(parsed.get("text") or "").strip()

    summary = ""
    elements: list[dict] = []
    if vision_model:
        try:
            vision_raw = await _image_completion(
                vision_model,
                item.image,
                (
                    "Опиши только достоверно видимое: тип материала, таблицы, "
                    "схемы, диаграммы, подписи, печати и другие важные элементы. "
                    "Не угадывай нечитаемое. "
                    'Верни JSON {"summary":"...",'
                    '"elements":[{"kind":"...","description":"..."}]}. '
                    "Не возвращай координаты."
                ),
            )
            vision = _json_or_text(vision_raw)
            summary = str(vision.get("summary") or vision.get("text") or "").strip()
            raw_elements = vision.get("elements")
            if isinstance(raw_elements, list):
                for value in raw_elements[:30]:
                    if not isinstance(value, dict):
                        continue
                    description = " ".join(
                        str(value.get("description") or "").split()
                    )[:600]
                    if description:
                        elements.append({
                            "kind": " ".join(
                                str(value.get("kind") or "элемент").split()
                            )[:80],
                            "description": description,
                        })
        except ValueError:
            pass
    return {"text": text, "visual_summary": summary, "elements": elements}


def _save_extraction(
    project_id: int,
    document_id: int,
    item: VisualItem,
    result: dict | None,
    *,
    ocr_model: str,
    vision_model: str | None,
    error: str | None = None,
) -> None:
    init_document_vision_db()
    now = utc_now()
    payload = result or {}
    with connect() as db:
        db.execute(
            """
            INSERT INTO document_visual_extractions(
              project_id,document_id,locator,page_number,source_kind,
              ocr_text,visual_summary,visual_elements_json,ocr_model_id,
              vision_model_id,status,error,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(document_id,locator) DO UPDATE SET
              page_number=excluded.page_number,
              source_kind=excluded.source_kind,
              ocr_text=excluded.ocr_text,
              visual_summary=excluded.visual_summary,
              visual_elements_json=excluded.visual_elements_json,
              ocr_model_id=excluded.ocr_model_id,
              vision_model_id=excluded.vision_model_id,
              status=excluded.status,
              error=excluded.error,
              updated_at=excluded.updated_at
            """,
            (
                project_id, document_id, item.locator, item.page_number, item.kind,
                str(payload.get("text") or ""),
                str(payload.get("visual_summary") or ""),
                json.dumps(payload.get("elements") or [], ensure_ascii=False),
                ocr_model, vision_model,
                "complete" if error is None else "failed",
                error, now, now,
            ),
        )


def _saved_blocks(project_id: int, document_id: int) -> list[DocumentBlock]:
    init_document_vision_db()
    with connect() as db:
        rows = db.execute(
            """
            SELECT locator,page_number,ocr_text,visual_summary,
                   visual_elements_json,ocr_model_id,vision_model_id
            FROM document_visual_extractions
            WHERE project_id=? AND document_id=? AND status='complete'
            ORDER BY COALESCE(page_number,999999),locator
            """,
            (project_id, document_id),
        ).fetchall()
    blocks: list[DocumentBlock] = []
    for row in rows:
        locator = str(row["locator"])
        text = str(row["ocr_text"] or "").strip()
        if text:
            blocks.append(
                DocumentBlock(
                    index=0,
                    kind="ocr",
                    text=text,
                    locator=locator,
                    title=(
                        f"OCR · страница {row['page_number']}"
                        if row["page_number"] else "OCR · " + locator
                    ),
                    metadata={
                        "ocr": True,
                        "model": row["ocr_model_id"],
                        "page": row["page_number"],
                        "bbox_verified": False,
                    },
                )
            )
        summary = str(row["visual_summary"] or "").strip()
        try:
            elements = json.loads(row["visual_elements_json"] or "[]")
        except json.JSONDecodeError:
            elements = []
        lines = [summary] if summary else []
        for element in elements[:30]:
            if isinstance(element, dict) and element.get("description"):
                lines.append(
                    f"{element.get('kind') or 'элемент'}: {element['description']}"
                )
        if lines:
            blocks.append(
                DocumentBlock(
                    index=0,
                    kind="visual",
                    text="\n".join(lines),
                    locator=locator + ":visual",
                    title="Визуальный анализ · " + locator,
                    metadata={
                        "vision": True,
                        "model": row["vision_model_id"],
                        "source_locator": locator,
                        "bbox_verified": False,
                    },
                )
            )
    return blocks


def _combined_structured(
    document: dict,
    data: bytes,
    visual_blocks: list[DocumentBlock],
    *,
    total_visual_items: int,
    completed_visual_items: int,
    page_count_hint: int,
) -> StructuredDocument:
    try:
        base = extract_structured_document(document["filename"], data)
        base_blocks = list(base.blocks)
        metadata = dict(base.metadata)
        title = base.title
        fmt = base.format
    except ValueError:
        base_blocks = []
        metadata = {"page_count": page_count_hint, "table_count": 0}
        title = Path(document["filename"]).stem
        fmt = Path(document["filename"]).suffix.lower().lstrip(".") or "image"

    replaced_locators = {
        str(block.locator) for block in visual_blocks if block.kind == "ocr"
    }
    blocks = [
        block for block in base_blocks
        if str(block.locator) not in replaced_locators
    ] + visual_blocks
    for index, block in enumerate(blocks):
        block.index = index

    extraction = dict(metadata.get("extraction") or {})
    details = dict(extraction.get("details") or {})
    page_count = int(
        metadata.get("page_count")
        or details.get("page_count")
        or page_count_hint
        or 0
    )
    suffix = Path(document["filename"]).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        page_count = max(1, page_count)

    if suffix == ".pdf":
        local_pages = int(details.get("text_pages") or 0)
        ocr_pages = len({
            int(block.metadata["page"])
            for block in visual_blocks
            if block.kind == "ocr" and block.metadata.get("page")
        })
        coverage = (local_pages + ocr_pages) / max(1, page_count)
    else:
        native = float(extraction.get("coverage") or (1.0 if base_blocks else 0.0))
        visual = (
            completed_visual_items / max(1, total_visual_items)
            if total_visual_items else 0.0
        )
        coverage = max(native, visual if not base_blocks else native)

    warnings = [
        str(item) for item in extraction.get("warnings") or []
        if "нужен ocr" not in str(item).lower()
    ]
    if completed_visual_items < total_visual_items:
        warnings.append(
            "Визуально обработана только часть выбранных элементов: "
            f"{completed_visual_items}/{total_visual_items}."
        )

    metadata.update({
        "page_count": page_count,
        "extraction": {
            "status": "vision_augmented" if visual_blocks else str(
                extraction.get("status") or "unknown"
            ),
            "coverage": max(0.0, min(1.0, coverage)),
            "warnings": warnings,
            "details": {
                **details,
                "visual_semantics_supported": bool(visual_blocks),
                "visual_items_requested": total_visual_items,
                "visual_items_completed": completed_visual_items,
                "bbox_verified": False,
            },
        },
    })
    return StructuredDocument(
        filename=document["filename"],
        format=fmt,
        title=title,
        text="\n\n".join(block.text for block in blocks if block.text).strip(),
        blocks=blocks,
        metadata=metadata,
    )


def _chunks_with_locators(structured: StructuredDocument) -> list[str]:
    result: list[str] = []
    for block in structured.blocks:
        pieces = chunk_text(block.text)
        if not pieces and block.text.strip():
            pieces = [block.text.strip()]
        for piece in pieces:
            result.append(f"[{block.locator}]\n{piece}")
    return result


async def run_document_vision(
    project_id: int,
    document_id: int,
    *,
    task_id: int | None = None,
    force: bool = False,
    max_items: int = 12,
    include_text_pages: bool = False,
) -> dict:
    init_document_vision_db()
    document = get_document(project_id, document_id)
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")
    path = resolve_data_path(document["stored_path"])
    if not path.exists() or not path.is_file():
        raise ValueError("Оригинал документа отсутствует на диске.")
    data = path.read_bytes()
    items, page_count = _visual_items(
        document["filename"], data, include_text_pages=include_text_pages
    )
    items = items[:max(1, min(int(max_items), MAX_VISUAL_ITEMS))]
    if not items:
        raise ValueError(
            "Не найдено страниц или изображений, которым нужен OCR/визуальный анализ."
        )

    _set_state(
        project_id, document_id, "running",
        requested=len(items), processed=0, failed=0,
        error=None,
    )
    try:
        ocr_model, vision_model = await _resolve_models()
    except Exception as exc:
        _set_state(
            project_id, document_id, "failed",
            requested=len(items), processed=0, failed=0,
            error=str(exc)[:1600],
        )
        raise
    _set_state(
        project_id, document_id, "running",
        requested=len(items), processed=0, failed=0,
        ocr_model=ocr_model, vision_model=vision_model,
    )
    processed = 0
    failed = 0

    for item in items:
        if task_id is not None and is_task_cancel_requested(task_id):
            _set_state(
                project_id, document_id, "cancelled",
                requested=len(items), processed=processed, failed=failed,
                ocr_model=ocr_model, vision_model=vision_model,
                error="Обработка отменена пользователем.",
            )
            return document_vision_status(project_id, document_id)

        if not force:
            with connect() as db:
                existing = db.execute(
                    """
                    SELECT status FROM document_visual_extractions
                    WHERE project_id=? AND document_id=? AND locator=?
                    """,
                    (project_id, document_id, item.locator),
                ).fetchone()
            if existing and existing["status"] == "complete":
                processed += 1
                continue

        try:
            result = await _analyze_item(
                item, ocr_model=ocr_model, vision_model=vision_model
            )
            _save_extraction(
                project_id, document_id, item, result,
                ocr_model=ocr_model, vision_model=vision_model,
            )
            processed += 1
        except Exception as exc:
            failed += 1
            _save_extraction(
                project_id, document_id, item, None,
                ocr_model=ocr_model, vision_model=vision_model,
                error=str(exc)[:1600],
            )

        _set_state(
            project_id, document_id, "running",
            requested=len(items), processed=processed, failed=failed,
            ocr_model=ocr_model, vision_model=vision_model,
        )

    visual_blocks = _saved_blocks(project_id, document_id)
    combined = _combined_structured(
        document, data, visual_blocks,
        total_visual_items=len(items),
        completed_visual_items=processed,
        page_count_hint=page_count,
    )
    if not combined.blocks:
        raise ValueError(
            "OCR не вернул пригодного текста или визуального описания."
        )

    replace_document_chunks(
        project_id, document_id, _chunks_with_locators(combined)
    )
    intelligence = build_local_document_intelligence(
        project_id, document_id, combined
    )
    # Refresh the same project RAG index after searchable chunks change.
    from .rag import init_rag
    init_rag()
    _set_state(
        project_id, document_id,
        "complete" if failed == 0 else "partial",
        requested=len(items), processed=processed, failed=failed,
        ocr_model=ocr_model, vision_model=vision_model,
        error=None if failed == 0 else f"Не удалось обработать элементов: {failed}.",
    )
    status = document_vision_status(project_id, document_id)
    status["intelligence"] = intelligence
    status["page_count"] = page_count
    return status
