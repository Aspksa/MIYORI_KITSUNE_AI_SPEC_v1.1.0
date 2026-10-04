"""Project-isolated multi-document exhaustive comparison, backed by existing Q&A tasks.

A comparison never claims to verify full original files if OCR/extraction is
incomplete. It keeps independently attributable document evidence, and it
never executes write-tools or fabricates a semantic contradiction.
"""
from __future__ import annotations
import json
from .db import connect,get_document,utc_now
from .document_questions import (
    enqueue_exhaustive_document_question, get_document_question,
)


def init_document_comparisons_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS document_comparisons(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            conversation_id INTEGER,
            question TEXT NOT NULL,
            documents_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id,conversation_id,question,documents_json)
        );
        CREATE TABLE IF NOT EXISTS document_comparison_items(
            comparison_id INTEGER NOT NULL REFERENCES document_comparisons(id) ON DELETE CASCADE,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES document_questions(id) ON DELETE CASCADE,
            PRIMARY KEY(comparison_id,document_id)
        );
        CREATE INDEX IF NOT EXISTS idx_doc_comparisons_project
          ON document_comparisons(project_id,created_at);
        """)


def enqueue_document_comparison(
    project_id: int, document_ids: list[int], question: str,
    *, conversation_id: int | None = None,
) -> dict:
    ids=sorted(set(int(value) for value in document_ids))
    if len(ids)!=len(document_ids) or not 2<=len(ids)<=5:
        raise ValueError("Выберите 2–5 разных документов.")
    query=" ".join(question.strip().split())
    if not query or len(query)>5000:
        raise ValueError("Вопрос должен содержать от 1 до 5000 символов.")
    with connect() as db:
        if conversation_id is not None:
            present=db.execute(
                "SELECT 1 FROM conversations WHERE id=? AND project_id=?",
                (conversation_id,project_id),
            ).fetchone()
            if not present:
                raise ValueError("Разговор не принадлежит выбранному проекту.")
    for did in ids:
        if not get_document(project_id,did):
            raise ValueError("Документ не найден в текущем проекте.")
    init_document_comparisons_db()
    encoded=json.dumps(ids)
    with connect() as db:
        row=db.execute("""
          SELECT id FROM document_comparisons
          WHERE project_id=? AND conversation_id IS ? AND question=? AND documents_json=?
        """,(project_id,conversation_id,query,encoded)).fetchone()
    if row:
        return get_document_comparison(project_id,int(row["id"]))
    # Schedule existing per-file exhaustive Q&A, including its own caching,
    # recovery and OCR checks. Never silently substitute truncated RAG.
    tasks=[]
    for did in ids:
        try:
            entry=enqueue_exhaustive_document_question(project_id,did,query)
            tasks.append((did,int(entry["id"])))
        except ValueError as exc:
            # Do not enqueue additional items on incomplete or unsafe extraction.
            raise ValueError(f"Документ {did}: {exc}") from exc
    with connect() as db:
        cur=db.execute("""
          INSERT INTO document_comparisons(
             project_id,conversation_id,question,documents_json,created_at
          ) VALUES(?,?,?,?,?)
        """,(project_id,conversation_id,query,encoded,utc_now()))
        cid=int(cur.lastrowid)
        db.executemany("""
          INSERT INTO document_comparison_items(comparison_id,document_id,question_id)
          VALUES(?,?,?)
        """,[(cid,did,qid) for did,qid in tasks])
    return get_document_comparison(project_id,cid)


def get_document_comparison(project_id: int, comparison_id: int) -> dict:
    init_document_comparisons_db()
    with connect() as db:
        row=db.execute("""
          SELECT * FROM document_comparisons WHERE id=? AND project_id=?
        """,(comparison_id,project_id)).fetchone()
        if not row:
            raise LookupError("Сравнение не найдено.")
        members=db.execute("""
          SELECT document_id,question_id FROM document_comparison_items
          WHERE comparison_id=? ORDER BY document_id
        """,(comparison_id,)).fetchall()
    results=[]
    for member in members:
        did,qid=int(member["document_id"]),int(member["question_id"])
        doc=get_document(project_id,did)
        question=get_document_question(project_id,did,qid)
        if not doc or not question:
            results.append({"document_id":did,"status":"unavailable","evidence":[]})
            continue
        answer=question.get("answer") or {}
        evidence=answer.get("evidence") or []
        if not isinstance(evidence,list):evidence=[]
        results.append({
            "document_id":did,"filename":doc["filename"],
            "question_id":qid,"task_id":question.get("task_id"),
            "status":question["status"],
            "answer":str(answer.get("answer") or "")[:5000],
            "evidence":[{
                "text":str(item.get("text") or "")[:900],
                "locator":str(item.get("locator") or "")[:180],
            } for item in evidence[:40] if isinstance(item,dict)
              and item.get("locator")],
            "coverage_ratio":question.get("overall_coverage_ratio"),
            "extraction_status":question.get("extraction_status"),
            "caveats":[str(s)[:500] for s in (answer.get("caveats") or [])[:10]],
            "error":question.get("last_error"),
        })
    statuses={s["status"] for s in results}
    terminal={"complete","partial","cancelled","failed","unavailable"}
    finished=bool(results) and all(status in terminal for status in statuses)
    incomplete=any(
        s["status"]!="complete" or
        (s.get("coverage_ratio") or 0)<0.995
        for s in results
    )
    return {
        "id":comparison_id,
        "project_id":project_id,
        "conversation_id":row["conversation_id"],
        "question":row["question"],
        "status":"partial" if finished and incomplete else
                 "complete" if finished else "working",
        "documents":results,
        "finished":finished,
        "full_originals_verified":False,
        "note":(
          "Сопоставлены независимые результаты чтения документов. "
          "Evidence привязано к исходным фрагментам. "
          "Полное покрытие извлечённого текста не доказывает полноту OCR "
          "или семантическую правильность выводов модели."
        ),
    }
