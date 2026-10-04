"""Owner-provided chat corrections with audit history and project isolation.

Corrections are owner statements, NOT verified project facts or new agent
instructions. No fine-tuning, automatic knowledge promotion or tool approval.
"""
from __future__ import annotations

import re
from .db import connect,utc_now

_VALID={"corrected","incorrect","useful"}
_WORDS=re.compile(r"[а-яёa-z0-9]{4,}",re.IGNORECASE)
_SKIP={"сделай","скажи","привет","спасибо","можешь","пожалуйста",
       "нужно","ответь","теперь","значит","было","написал","ответа"}


def init_chat_feedback_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS chat_feedback_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            verdict TEXT NOT NULL CHECK(verdict IN ('corrected','incorrect','useful')),
            correction TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(project_id,message_id,verdict,correction)
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_project
          ON chat_feedback_events(project_id,id);
        """)


def record_chat_feedback(
    project_id: int,conversation_id: int,message_id: int,
    verdict: str,correction: str = "",
) -> dict:
    value=str(correction or "").strip()
    if verdict not in _VALID:
        raise ValueError("Недопустимый тип обратной связи.")
    if verdict=="corrected" and not value:
        raise ValueError("Введите исправление ответа.")
    if len(value)>2000:
        raise ValueError("Исправление не должно превышать 2000 символов.")
    init_chat_feedback_db()
    with connect() as db:
        match=db.execute("""
            SELECT m.id,m.role FROM messages m
            JOIN conversations c ON c.id=m.conversation_id
            WHERE m.id=? AND m.conversation_id=? AND c.project_id=?
        """,(message_id,conversation_id,project_id)).fetchone()
        if not match or match["role"]!="assistant":
            raise LookupError("Ответ для обратной связи не найден в этом проекте.")
        db.execute("""
            INSERT INTO chat_feedback_events(
              project_id,conversation_id,message_id,verdict,correction,created_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(project_id,message_id,verdict,correction) DO NOTHING
        """,(project_id,conversation_id,message_id,verdict,value,utc_now()))
        row=db.execute("""
            SELECT * FROM chat_feedback_events
            WHERE project_id=? AND message_id=? AND verdict=? AND correction=?
            ORDER BY id DESC LIMIT 1
        """,(project_id,message_id,verdict,value)).fetchone()
    return dict(row)


def relevant_owner_corrections(
    project_id: int,query: str,limit: int = 4,
) -> list[dict]:
    """Only explicitly corrected prior model answers in *this* project."""
    tokens={
        term.casefold() for term in _WORDS.findall(str(query)[:1800])
        if term.casefold() not in _SKIP
    }
    if not tokens:return []
    init_chat_feedback_db()
    with connect() as db:
        rows=db.execute("""
            SELECT f.id,f.message_id,f.conversation_id,f.correction,f.created_at,
              m.content AS original_answer,
              (SELECT u.content FROM messages u
                 WHERE u.conversation_id=m.conversation_id
                   AND u.role='user' AND u.id<m.id
                 ORDER BY u.id DESC LIMIT 1) AS original_question
            FROM chat_feedback_events f
            JOIN messages m ON m.id=f.message_id
            JOIN conversations c ON c.id=f.conversation_id
            WHERE f.project_id=? AND c.project_id=? AND f.verdict='corrected'
            ORDER BY f.id DESC LIMIT 500
        """,(project_id,project_id)).fetchall()
    ranked=[]
    seen_messages=set()
    for row in rows:
        data=dict(row)
        if data["message_id"] in seen_messages:
            continue
        seen_messages.add(data["message_id"])
        text=" ".join((
            str(data.get("original_question") or ""),
            str(data.get("original_answer") or ""),
            str(data.get("correction") or ""),
        )).casefold()
        score=sum(term in text for term in tokens)
        if score:
            ranked.append((score,int(data["id"]),data))
    ranked.sort(key=lambda row:(row[0],row[1]),reverse=True)
    result=[]
    for _,_,entry in ranked[:max(1,min(limit,6))]:
        result.append({
            "original_question":str(entry.get("original_question") or "")[:350],
            "incorrect_answer":str(entry.get("original_answer") or "")[:350],
            "owner_correction":str(entry["correction"])[:2000],
            "message_id":entry["message_id"],
            "conversation_id":entry["conversation_id"],
            "created_at":entry["created_at"],
            "verification":"owner_statement_unverified",
        })
    return result



def chat_quality_summary(project_id: int, days: int = 30) -> dict:
    """Observable chat quality signals; never an invented accuracy score."""
    days = max(1, min(365, int(days)))
    init_chat_feedback_db()
    window = f"-{days} days"
    with connect() as db:
        row = db.execute(
            """
            SELECT
              COUNT(*) AS answers,
              SUM(CASE
                WHEN json_valid(m.metadata_json)
                 AND COALESCE(json_array_length(json_extract(m.metadata_json,'$.sources')),0) > 0
                THEN 1 ELSE 0 END) AS source_backed,
              SUM(CASE
                WHEN json_valid(m.metadata_json)
                 AND COALESCE(json_extract(m.metadata_json,'$.diagnostics.numeric_check.missing_source'),0) > 0
                THEN 1 ELSE 0 END) AS numeric_warnings,
              SUM(CASE
                WHEN json_valid(m.metadata_json)
                 AND json_extract(m.metadata_json,'$.diagnostics.evidence.status')
                    IN ('missing_extraction','partial_extraction','insufficient_sources')
                THEN 1 ELSE 0 END) AS evidence_limited,
              SUM(CASE
                WHEN json_valid(m.metadata_json)
                 AND json_extract(m.metadata_json,'$.diagnostics.model_usage.latency_ms') IS NOT NULL
                THEN 1 ELSE 0 END) AS measured_model_usage
            FROM messages m
            JOIN conversations c ON c.id=m.conversation_id
            WHERE c.project_id=? AND m.role='assistant'
              AND julianday(m.created_at) >= julianday('now', ?)
            """,
            (project_id, window),
        ).fetchone()
        feedback_rows = db.execute(
            """
            SELECT verdict,COUNT(*) AS events
            FROM chat_feedback_events
            WHERE project_id=?
              AND julianday(created_at) >= julianday('now', ?)
            GROUP BY verdict
            """,
            (project_id, window),
        ).fetchall()
    feedback_counts = {
        str(item["verdict"]): int(item["events"])
        for item in feedback_rows
    }
    return {
        "days": days,
        "answers": int(row["answers"] or 0),
        "source_backed": int(row["source_backed"] or 0),
        "numeric_warnings": int(row["numeric_warnings"] or 0),
        "evidence_limited": int(row["evidence_limited"] or 0),
        "measured_model_usage": int(row["measured_model_usage"] or 0),
        "feedback": {
            "corrected": feedback_counts.get("corrected", 0),
            "incorrect": feedback_counts.get("incorrect", 0),
            "useful": feedback_counts.get("useful", 0),
        },
        "accuracy_score": None,
        "quality_accuracy_measured": False,
        "note": (
            "Это наблюдаемые сигналы качества и обратная связь владельца, "
            "а не независимая оценка точности модели."
        ),
    }

def feedback_totals(project_id: int) -> dict:
    init_chat_feedback_db()
    with connect() as db:
        rows=db.execute("""
            SELECT verdict,COUNT(*) AS events FROM chat_feedback_events
            WHERE project_id=? GROUP BY verdict
        """,(project_id,)).fetchall()
    totals={item["verdict"]:int(item["events"]) for item in rows}
    return {
        "corrected":totals.get("corrected",0),
        "incorrect":totals.get("incorrect",0),
        "useful":totals.get("useful",0),
        "quality_accuracy_measured":False,
        "note":"Явная обратная связь пользователя, не независимый показатель точности модели.",
    }
