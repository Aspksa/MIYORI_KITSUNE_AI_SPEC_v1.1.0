from __future__ import annotations

from .db import connect, utc_now

CHAT_PROGRESS_STAGES = {
    "accepted",
    "agent",
    "retrieving",
    "generating",
    "verifying",
    "completed",
    "cancelled",
    "error",
}


def init_chat_progress_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_request_progress(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                request_id TEXT NOT NULL,
                conversation_id INTEGER,
                user_message_id INTEGER,
                stage TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id, request_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_progress_updated
              ON chat_request_progress(project_id, updated_at);
            """
        )


def set_chat_progress(
    project_id: int,
    request_id: str | None,
    stage: str,
    detail: str,
    *,
    conversation_id: int | None = None,
    user_message_id: int | None = None,
) -> None:
    if not request_id:
        return
    if stage not in CHAT_PROGRESS_STAGES:
        raise ValueError("Недопустимая стадия обработки чата.")
    init_chat_progress_db()
    with connect() as db:
        db.execute(
            """
            INSERT INTO chat_request_progress(
                project_id, request_id, conversation_id, user_message_id,
                stage, detail, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(project_id, request_id) DO UPDATE SET
                conversation_id=COALESCE(excluded.conversation_id, conversation_id),
                user_message_id=COALESCE(excluded.user_message_id, user_message_id),
                stage=excluded.stage,
                detail=excluded.detail,
                updated_at=excluded.updated_at
            """,
            (
                project_id,
                request_id,
                conversation_id,
                user_message_id,
                stage,
                str(detail or "")[:240],
                utc_now(),
            ),
        )


def get_chat_progress(project_id: int, request_id: str) -> dict | None:
    init_chat_progress_db()
    with connect() as db:
        row = db.execute(
            """
            SELECT project_id, request_id, conversation_id, user_message_id,
                   stage, detail, updated_at
            FROM chat_request_progress
            WHERE project_id=? AND request_id=?
            """,
            (project_id, request_id),
        ).fetchone()
    return dict(row) if row else None
