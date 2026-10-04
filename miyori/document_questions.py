from __future__ import annotations

import hashlib
import json

from .config import settings
from .db import (
    connect,
    create_task,
    get_document,
    is_task_cancel_requested,
    record_audit_event,
    record_task_event,
    utc_now,
)
from .document_intelligence import (
    build_document_windows,
    get_document_intelligence,
)
from .provider import (
    analyze_document_question_window,
    synthesize_exhaustive_document_answer,
)


QUESTION_ENGINE_VERSION = "1.1.0"


def init_document_questions_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                task_id INTEGER,
                source_sha256 TEXT NOT NULL,
                question TEXT NOT NULL,
                question_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'queued','analyzing','complete','partial','cancelled','failed'
                )),
                scanned_chars INTEGER NOT NULL DEFAULT 0,
                total_chars INTEGER NOT NULL DEFAULT 0,
                coverage_ratio REAL NOT NULL DEFAULT 0.0,
                extraction_status TEXT NOT NULL DEFAULT 'unknown',
                extraction_coverage REAL NOT NULL DEFAULT 0.0,
                overall_coverage_ratio REAL NOT NULL DEFAULT 0.0,
                answer_json TEXT NOT NULL DEFAULT '{}',
                model_id TEXT,
                engine_version TEXT NOT NULL,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS document_question_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                window_index INTEGER NOT NULL,
                source_fingerprint TEXT NOT NULL,
                source_chars INTEGER NOT NULL,
                locator_start TEXT,
                locator_end TEXT,
                relevant INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL DEFAULT '{}',
                model_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(question_id, window_index),
                FOREIGN KEY(question_id) REFERENCES document_questions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_document_questions_document
                ON document_questions(project_id, document_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_document_questions_hash
                ON document_questions(document_id, source_sha256, question_hash, status);
            CREATE INDEX IF NOT EXISTS idx_document_question_windows_question
                ON document_question_windows(question_id, window_index);
            """
        )
        question_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(document_questions)"
            ).fetchall()
        }
        extraction_columns = {
            "extraction_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "extraction_coverage": "REAL NOT NULL DEFAULT 0.0",
            "overall_coverage_ratio": "REAL NOT NULL DEFAULT 0.0",
        }
        for column, ddl in extraction_columns.items():
            if column not in question_columns:
                conn.execute(
                    f"ALTER TABLE document_questions ADD COLUMN {column} {ddl}"
                )


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _normalize_question(question: str) -> str:
    clean = " ".join(str(question or "").strip().split())
    if not clean:
        raise ValueError("Вопрос к документу пустой.")
    if len(clean) > 5000:
        raise ValueError("Вопрос к документу слишком длинный.")
    return clean


def _question_hash(question: str) -> str:
    return hashlib.sha256(question.casefold().encode("utf-8")).hexdigest()


def _question_row(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["coverage_ratio"] = float(item.get("coverage_ratio") or 0.0)
    item["extraction_coverage"] = float(
        item.get("extraction_coverage") or 0.0
    )
    item["overall_coverage_ratio"] = float(
        item.get("overall_coverage_ratio") or 0.0
    )
    item["answer"] = _loads(item.pop("answer_json", None), {})
    return item


def get_document_question(
    project_id: int,
    document_id: int,
    question_id: int,
) -> dict | None:
    init_document_questions_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM document_questions
            WHERE id = ? AND project_id = ? AND document_id = ?
            """,
            (question_id, project_id, document_id),
        ).fetchone()
    return _question_row(row)


def list_document_questions(
    project_id: int,
    document_id: int,
    *,
    limit: int = 30,
) -> list[dict]:
    init_document_questions_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM document_questions
            WHERE project_id = ? AND document_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, document_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_question_row(row) for row in rows]


def list_document_question_windows(
    project_id: int,
    document_id: int,
    question_id: int,
) -> list[dict]:
    question = get_document_question(project_id, document_id, question_id)
    if not question:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM document_question_windows
            WHERE question_id = ?
            ORDER BY window_index ASC
            """,
            (question_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["relevant"] = bool(item["relevant"])
        item["result"] = _loads(item.pop("result_json", None), {})
        result.append(item)
    return result


def enqueue_exhaustive_document_question(
    project_id: int,
    document_id: int,
    question: str,
    *,
    force: bool = False,
) -> dict:
    init_document_questions_db()
    document = get_document(project_id, document_id)
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")

    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        _, _ = build_document_windows(project_id, document_id)
        profile = get_document_intelligence(project_id, document_id)
    if profile and profile.get("status") in {"needs_ocr", "unsupported"}:
        raise ValueError(
            profile.get("last_error")
            or "Полный вопрос по документу невозможен без извлечённого текста."
        )

    clean = _normalize_question(question)
    digest = _question_hash(clean)

    if not force:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM document_questions
                WHERE project_id = ?
                  AND document_id = ?
                  AND source_sha256 = ?
                  AND question_hash = ?
                  AND status IN ('queued','analyzing','complete')
                ORDER BY CASE status
                    WHEN 'analyzing' THEN 0
                    WHEN 'queued' THEN 1
                    ELSE 2
                END, id DESC
                LIMIT 1
                """,
                (project_id, document_id, document["sha256"], digest),
            ).fetchone()
        if row:
            existing = _question_row(row) or {}
            existing["existing"] = True
            return existing

    if not force:
        with connect() as conn:
            retry_row = conn.execute(
                """
                SELECT *
                FROM document_questions
                WHERE project_id = ?
                  AND document_id = ?
                  AND source_sha256 = ?
                  AND question_hash = ?
                  AND status IN ('partial','failed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (project_id, document_id, document["sha256"], digest),
            ).fetchone()
        if retry_row:
            retry_item = _question_row(retry_row) or {}
            retry_id = int(retry_item["id"])
            task = create_task(
                project_id,
                "document_question",
                {
                    "document_id": document_id,
                    "question_id": retry_id,
                },
            )
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE document_questions
                    SET task_id = ?, status = 'queued', last_error = NULL,
                        updated_at = ?, finished_at = NULL
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        int(task["id"]),
                        utc_now(),
                        retry_id,
                        project_id,
                    ),
                )
            result = get_document_question(
                project_id,
                document_id,
                retry_id,
            ) or {}
            result["existing"] = True
            result["retrying"] = True
            return result

    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO document_questions(
                project_id, document_id, source_sha256, question,
                question_hash, status, extraction_status,
                extraction_coverage, overall_coverage_ratio,
                engine_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, 0.0, ?, ?, ?)
            """,
            (
                project_id,
                document_id,
                document["sha256"],
                clean,
                digest,
                str((profile or {}).get("extraction_status") or "unknown"),
                float((profile or {}).get("extraction_coverage") or 0.0),
                QUESTION_ENGINE_VERSION,
                now,
                now,
            ),
        )
        question_id = int(cur.lastrowid)

    task = create_task(
        project_id,
        "document_question",
        {
            "document_id": document_id,
            "question_id": question_id,
        },
    )
    with connect() as conn:
        conn.execute(
            """
            UPDATE document_questions
            SET task_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (int(task["id"]), utc_now(), question_id),
        )

    record_audit_event(
        project_id,
        "user",
        "document.question.queued",
        "Запущена полная проверка документа по вопросу пользователя.",
        entity_type="document_question",
        entity_id=question_id,
        details={
            "document_id": document_id,
            "task_id": task["id"],
            "question": clean[:500],
        },
    )
    result = get_document_question(project_id, document_id, question_id) or {}
    result["existing"] = False
    return result


def _save_question_window(
    question_id: int,
    window_index: int,
    window: dict,
    result: dict,
) -> None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO document_question_windows(
                question_id, window_index, source_fingerprint, source_chars,
                locator_start, locator_end, relevant, result_json,
                model_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id, window_index) DO UPDATE SET
                source_fingerprint = excluded.source_fingerprint,
                source_chars = excluded.source_chars,
                locator_start = excluded.locator_start,
                locator_end = excluded.locator_end,
                relevant = excluded.relevant,
                result_json = excluded.result_json,
                model_id = excluded.model_id,
                updated_at = excluded.updated_at
            """,
            (
                question_id,
                window_index,
                window["source_fingerprint"],
                int(window["source_chars"]),
                window.get("locator_start"),
                window.get("locator_end"),
                int(bool(result.get("relevant"))),
                json.dumps(result, ensure_ascii=False),
                settings.cloudru_model_id,
                now,
                now,
            ),
        )


async def run_exhaustive_document_question(
    project_id: int,
    question_id: int,
    *,
    task_id: int | None = None,
) -> dict:
    init_document_questions_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM document_questions
            WHERE id = ? AND project_id = ?
            """,
            (question_id, project_id),
        ).fetchone()
    question = _question_row(row)
    if not question:
        raise ValueError("Запрос полного анализа документа не найден.")

    document_id = int(question["document_id"])
    document = get_document(project_id, document_id)
    if not document:
        raise ValueError("Документ больше не существует в текущем проекте.")
    if document["sha256"] != question["source_sha256"]:
        raise RuntimeError(
            "Оригинал документа изменился после постановки вопроса; "
            "запустите проверку заново."
        )

    profile, windows = build_document_windows(project_id, document_id)
    total_chars = max(1, sum(int(window["source_chars"]) for window in windows))
    extraction_status = str(profile.get("extraction_status") or "unknown")
    extraction_coverage = max(
        0.0,
        min(1.0, float(profile.get("extraction_coverage") or 0.0)),
    )

    with connect() as conn:
        existing_rows = conn.execute(
            """
            SELECT *
            FROM document_question_windows
            WHERE question_id = ?
            ORDER BY window_index ASC
            """,
            (question_id,),
        ).fetchall()
        existing = {
            int(row["window_index"]): dict(row)
            for row in existing_rows
        }
        conn.execute(
            """
            UPDATE document_questions
            SET status = 'analyzing', total_chars = ?, scanned_chars = 0,
                coverage_ratio = 0.0, extraction_status = ?,
                extraction_coverage = ?, overall_coverage_ratio = 0.0,
                model_id = ?, last_error = NULL,
                updated_at = ?, finished_at = NULL
            WHERE id = ? AND project_id = ?
            """,
            (
                total_chars,
                extraction_status,
                extraction_coverage,
                settings.cloudru_model_id,
                utc_now(),
                question_id,
                project_id,
            ),
        )

    record_audit_event(
        project_id,
        "miyori",
        "document.question.started",
        "Miyori начала полную проверку документа по вопросу.",
        entity_type="document_question",
        entity_id=question_id,
        details={
            "document_id": document_id,
            "windows_total": len(windows),
        },
    )

    window_results: list[dict] = []
    scanned_chars = 0
    try:
        for index, window in enumerate(windows, start=1):
            if task_id is not None and is_task_cancel_requested(task_id):
                coverage = min(1.0, scanned_chars / total_chars)
                with connect() as conn:
                    conn.execute(
                        """
                        UPDATE document_questions
                        SET status = 'cancelled', scanned_chars = ?,
                            coverage_ratio = ?, updated_at = ?, finished_at = ?
                        WHERE id = ? AND project_id = ?
                        """,
                        (
                            scanned_chars,
                            coverage,
                            utc_now(),
                            utc_now(),
                            question_id,
                            project_id,
                        ),
                    )
                return get_document_question(
                    project_id, document_id, question_id
                ) or {}

            saved = existing.get(index)
            result = None
            if (
                saved
                and str(saved.get("source_fingerprint") or "")
                    == str(window["source_fingerprint"])
                and int(saved.get("source_chars") or -1)
                    == int(window["source_chars"])
            ):
                candidate = _loads(saved.get("result_json"), {})
                if candidate:
                    result = candidate

            if result is None:
                result = await analyze_document_question_window(
                    profile.get("title") or document["filename"],
                    question["question"],
                    index,
                    len(windows),
                    window["content"],
                )
                result["window_index"] = index
                result["locator_start"] = window.get("locator_start")
                result["locator_end"] = window.get("locator_end")
                _save_question_window(
                    question_id,
                    index,
                    window,
                    result,
                )

            window_results.append(result)
            scanned_chars += int(window["source_chars"])
            coverage = min(1.0, scanned_chars / total_chars)
            overall_coverage = coverage * extraction_coverage
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE document_questions
                    SET scanned_chars = ?, coverage_ratio = ?,
                        overall_coverage_ratio = ?, updated_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        scanned_chars,
                        coverage,
                        overall_coverage,
                        utc_now(),
                        question_id,
                        project_id,
                    ),
                )
            if task_id is not None:
                record_task_event(
                    task_id,
                    "progress",
                    json.dumps(
                        {
                            "question_id": question_id,
                            "document_id": document_id,
                            "window": index,
                            "windows_total": len(windows),
                            "coverage_ratio": round(coverage, 6),
                            "relevant": bool(result.get("relevant")),
                        },
                        ensure_ascii=False,
                    ),
                )

        coverage = min(1.0, scanned_chars / total_chars)
        answer = await synthesize_exhaustive_document_answer(
            profile.get("title") or document["filename"],
            question["question"],
            window_results,
            coverage_ratio=coverage,
        )
        overall_coverage = coverage * extraction_coverage
        answer["coverage_ratio"] = coverage
        answer["scan_coverage_ratio"] = coverage
        answer["source_extraction_status"] = extraction_status
        answer["source_extraction_coverage"] = extraction_coverage
        answer["overall_coverage_ratio"] = overall_coverage
        answer["source_extraction_warnings"] = (
            profile.get("extraction_warnings") or []
        )[:50]
        answer["windows_scanned"] = len(windows)
        answer["windows_relevant"] = sum(
            1 for item in window_results if item.get("relevant")
        )
        answer["document_id"] = document_id
        answer["question_id"] = question_id

        if extraction_status != "complete" or extraction_coverage < 0.995:
            caveat = (
                "Полностью проверен только извлечённый текст. "
                f"Из оригинала извлечено примерно {extraction_coverage * 100:.1f}%; "
                "неизвлечённые страницы/изображения/диаграммы могут содержать "
                "дополнительную информацию."
            )
            caveats = list(answer.get("caveats") or [])
            if caveat not in caveats:
                caveats.insert(0, caveat)
            answer["caveats"] = caveats[:80]
            if answer.get("confidence") == "high":
                answer["confidence"] = "medium"

        status = "complete" if coverage >= 0.995 else "partial"
        now = utc_now()
        with connect() as conn:
            conn.execute(
                """
                UPDATE document_questions
                SET status = ?, scanned_chars = ?, total_chars = ?,
                    coverage_ratio = ?, extraction_status = ?,
                    extraction_coverage = ?, overall_coverage_ratio = ?,
                    answer_json = ?, model_id = ?,
                    last_error = NULL, updated_at = ?, finished_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    status,
                    scanned_chars,
                    total_chars,
                    coverage,
                    extraction_status,
                    extraction_coverage,
                    overall_coverage,
                    json.dumps(answer, ensure_ascii=False),
                    settings.cloudru_model_id,
                    now,
                    now,
                    question_id,
                    project_id,
                ),
            )

        record_audit_event(
            project_id,
            "miyori",
            "document.question.completed",
            "Miyori завершила полную проверку документа по вопросу.",
            entity_type="document_question",
            entity_id=question_id,
            details={
                "document_id": document_id,
                "coverage_ratio": coverage,
                "extraction_coverage": extraction_coverage,
                "overall_coverage_ratio": overall_coverage,
                "windows_total": len(windows),
                "windows_relevant": answer["windows_relevant"],
            },
        )
        return get_document_question(
            project_id, document_id, question_id
        ) or {}

    except Exception as exc:
        coverage = min(1.0, scanned_chars / total_chars)
        overall_coverage = coverage * extraction_coverage
        status = "partial" if scanned_chars else "failed"
        with connect() as conn:
            conn.execute(
                """
                UPDATE document_questions
                SET status = ?, scanned_chars = ?, total_chars = ?,
                    coverage_ratio = ?, extraction_status = ?,
                    extraction_coverage = ?, overall_coverage_ratio = ?,
                    last_error = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    status,
                    scanned_chars,
                    total_chars,
                    coverage,
                    extraction_status,
                    extraction_coverage,
                    overall_coverage,
                    str(exc)[:2000],
                    utc_now(),
                    question_id,
                    project_id,
                ),
            )
        record_audit_event(
            project_id,
            "system",
            "document.question.failed",
            "Полная проверка документа остановилась с ошибкой.",
            entity_type="document_question",
            entity_id=question_id,
            details={
                "document_id": document_id,
                "coverage_ratio": coverage,
                "error": str(exc)[:1000],
            },
        )
        raise
