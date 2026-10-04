from __future__ import annotations

import json
import sqlite3

from .db import connect, get_conversation


MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_CHARS = 36_000


def init_conversation_ui_db() -> None:
    """Additive migrations: never rewrite existing messages or projects."""
    with connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "pinned" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_page "
            "ON messages(conversation_id, id DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_bookmarks (
                project_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(project_id, message_id),
                FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
            """
        )


def list_chat_conversations(project_id: int, query: str = "") -> list[dict]:
    term = query.strip()[:120]
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.pinned,
                   COALESCE(MAX(m.created_at), c.created_at) AS updated_at,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.project_id = ?
            GROUP BY c.id
            ORDER BY c.pinned DESC, updated_at DESC, c.id DESC
            """,
            (project_id,),
        ).fetchall()
        results = [dict(row) for row in rows]
        if not term:
            return results
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        matches = conn.execute(
            """
            SELECT DISTINCT m.conversation_id FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.project_id = ? AND m.content LIKE ? ESCAPE '\\'
            """,
            (project_id, pattern),
        ).fetchall()
        match_ids = {int(row["conversation_id"]) for row in matches}
        attached_matches = conn.execute(
            """
            SELECT DISTINCT m.conversation_id
            FROM messages m JOIN conversations c ON c.id = m.conversation_id
            JOIN json_each(
                CASE WHEN json_valid(m.metadata_json) THEN m.metadata_json ELSE '{}' END,
                '$.attachments'
            ) a
            JOIN documents d ON d.id = CAST(a.value AS INTEGER)
              AND d.project_id = c.project_id AND d.deleted_at IS NULL
            WHERE c.project_id = ? AND d.filename LIKE ? ESCAPE '\\'
            """,
            (project_id, pattern),
        ).fetchall()
        match_ids.update(int(row["conversation_id"]) for row in attached_matches)
        return [
            row for row in results
            if int(row["id"]) in match_ids or term.casefold() in str(row["title"]).casefold()
        ]


def update_chat_conversation(project_id: int, conversation_id: int, *, title: str | None = None, pinned: bool | None = None) -> dict:
    if title is None and pinned is None:
        raise ValueError("Не указаны изменения.")
    if title is not None:
        title = title.strip()
        if not 1 <= len(title) <= 100:
            raise ValueError("Название должно содержать от 1 до 100 символов.")
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND project_id = ?",
            (conversation_id, project_id),
        ).fetchone()
        if row is None:
            raise LookupError("Разговор не найден в выбранном проекте.")
        if title is not None:
            conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND project_id = ?",
                (title, conversation_id, project_id),
            )
        if pinned is not None:
            conn.execute(
                "UPDATE conversations SET pinned = ? WHERE id = ? AND project_id = ?",
                (int(pinned), conversation_id, project_id),
            )
        result = conn.execute(
            "SELECT id, title, pinned, created_at FROM conversations WHERE id = ? AND project_id = ?",
            (conversation_id, project_id),
        ).fetchone()
        return dict(result)


def chat_message_page(project_id: int, conversation_id: int, *, before_id: int | None = None, limit: int = 80) -> dict:
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    limit = max(1, min(100, int(limit)))
    params: list[int] = [project_id, conversation_id]
    condition = ""
    if before_id is not None:
        condition = "AND m.id < ?"
        params.append(before_id)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT m.id, m.role, m.content, m.metadata_json, m.created_at,
                   CASE WHEN b.message_id IS NULL THEN 0 ELSE 1 END AS bookmarked
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            LEFT JOIN message_bookmarks b ON b.project_id = c.project_id AND b.message_id = m.id
            WHERE c.project_id = ? AND c.id = ? {condition}
            ORDER BY m.id DESC LIMIT ?
            """,
            [*params, limit + 1],
        ).fetchall()
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    messages = []
    for row in rows:
        item = dict(row)
        raw = item.pop("metadata_json", None)
        try:
            item["metadata"] = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            item["metadata"] = {}
        item["bookmarked"] = bool(item["bookmarked"])
        messages.append(item)
    return {
        "messages": messages,
        "has_more": has_more,
        "before_id": messages[0]["id"] if has_more and messages else None,
    }


def set_message_bookmark(project_id: int, conversation_id: int, message_id: int, bookmarked: bool) -> dict:
    with connect() as conn:
        found = conn.execute(
            """
            SELECT m.id FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = ? AND m.conversation_id = ? AND c.project_id = ? AND m.role = 'assistant'
            """,
            (message_id, conversation_id, project_id),
        ).fetchone()
        if not found:
            raise LookupError("Ответ не найден в этом разговоре.")
        if bookmarked:
            conn.execute(
                "INSERT OR IGNORE INTO message_bookmarks(project_id, message_id) VALUES (?, ?)",
                (project_id, message_id),
            )
        else:
            conn.execute(
                "DELETE FROM message_bookmarks WHERE project_id = ? AND message_id = ?",
                (project_id, message_id),
            )
    return {"message_id": message_id, "bookmarked": bool(bookmarked)}


def fork_conversation_before_message(project_id: int, conversation_id: int, message_id: int) -> dict:
    """Fork immutable history without redoing tools, approvals or memory capture."""
    with connect() as conn:
        conversation = conn.execute(
            "SELECT title FROM conversations WHERE project_id = ? AND id = ?",
            (project_id, conversation_id),
        ).fetchone()
        if not conversation:
            raise LookupError("Разговор не найден.")
        pivot = conn.execute(
            "SELECT id, role FROM messages WHERE conversation_id = ? AND id = ?",
            (conversation_id, message_id),
        ).fetchone()
        if not pivot:
            raise LookupError("Сообщение не найдено.")
        if pivot["role"] not in ("user", "assistant"):
            raise ValueError("Можно продолжить только пользовательский вопрос или ответ.")
        # Rerun an assistant reply starting from the matching preceding user prompt.
        if pivot["role"] == "assistant":
            pivot = conn.execute(
                """
                SELECT id, role FROM messages
                WHERE conversation_id = ? AND id < ? AND role = 'user'
                ORDER BY id DESC LIMIT 1
                """,
                (conversation_id, message_id),
            ).fetchone()
            if not pivot:
                raise ValueError("Предыдущий пользовательский вопрос не найден.")
        source_user = conn.execute(
            "SELECT content, metadata_json FROM messages WHERE id = ? AND conversation_id = ?",
            (pivot["id"], conversation_id),
        ).fetchone()
        cur = conn.execute(
            "INSERT INTO conversations(project_id, title, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (project_id, (str(conversation["title"])[:85] + " · вариант")[:100]),
        )
        new_id = int(cur.lastrowid)
        earlier = conn.execute(
            """
            SELECT role, content, metadata_json FROM messages
            WHERE conversation_id = ? AND id < ? ORDER BY id
            """,
            (conversation_id, pivot["id"]),
        ).fetchall()
        for item in earlier:
            conn.execute(
                """
                INSERT INTO messages(conversation_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (new_id, item["role"], item["content"], item["metadata_json"]),
            )
        try:
            metadata = json.loads(source_user["metadata_json"] or "{}")
        except (ValueError, TypeError):
            metadata = {}
        return {
            "conversation_id": new_id,
            "message": source_user["content"],
            "attachments": metadata.get("attachments", []),
        }


def attached_document_context(project_id: int, ids: list[int]) -> tuple[list[dict], list[dict]]:
    if len(ids) > MAX_ATTACHMENT_COUNT or len(set(ids)) != len(ids):
        raise ValueError("Можно выбрать до пяти разных документов.")
    if not ids:
        return [], []
    documents, sources = [], []
    remaining = MAX_ATTACHMENT_CHARS
    with connect() as conn:
        for document_id in ids:
            row = conn.execute(
                """
                SELECT id, filename FROM documents
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (document_id, project_id),
            ).fetchone()
            if not row:
                raise ValueError("Документ не найден в текущем проекте.")
            chunks = conn.execute(
                """
                SELECT chunk_index, content FROM document_chunks
                WHERE document_id = ? ORDER BY chunk_index
                """,
                (document_id,),
            ).fetchall()
            used = []
            per_file = min(9_000, remaining)
            for chunk in chunks:
                if per_file <= 0:
                    break
                content = str(chunk["content"])[:per_file]
                if not content:
                    continue
                documents.append({
                    "filename": str(row["filename"]),
                    "chunk_index": int(chunk["chunk_index"]),
                    "content": content,
                })
                used.append(int(chunk["chunk_index"]))
                per_file -= len(content)
                remaining -= len(content)
            sources.append({
                "source_type": "document",
                "title": row["filename"],
                "locator": f"document:{document_id}",
                "document_id": int(document_id),
                "chunk_indexes": used,
                "download_url": f"/api/projects/{project_id}/documents/{document_id}/download",
                "readable": bool(chunks),
                "truncated": len(chunks) > len(used),
            })
    return documents, sources


def search_conversation_messages(
    project_id: int, conversation_id: int, query: str, *, limit: int = 40
) -> list[dict]:
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    term = query.strip()[:120]
    if not term:
        return []
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = "%" + escaped + "%"
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.role, substr(m.content,1,280) AS preview, m.created_at
            FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE c.project_id = ? AND c.id = ?
              AND (
                m.content LIKE ? ESCAPE '\\'
                OR EXISTS (
                    SELECT 1 FROM json_each(
                        CASE WHEN json_valid(m.metadata_json) THEN m.metadata_json ELSE '{}' END,
                        '$.attachments'
                    ) a
                    JOIN documents d ON d.id = CAST(a.value AS INTEGER)
                      AND d.project_id = c.project_id AND d.deleted_at IS NULL
                    WHERE d.filename LIKE ? ESCAPE '\\'
                )
              )
            ORDER BY m.id DESC LIMIT ?
            """,
            (project_id, conversation_id, pattern, pattern, min(60, max(1, limit))),
        ).fetchall()
    return [dict(row) for row in rows]


def list_bookmarked_messages(project_id: int, *, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.conversation_id, substr(m.content,1,240) AS preview,
                   c.title AS conversation_title, b.created_at,
                   COALESCE((
                     SELECT json_group_array(t.tag)
                     FROM chat_message_tags t
                     WHERE t.project_id=b.project_id AND t.message_id=m.id
                   ), '[]') AS tags_json
            FROM message_bookmarks b
            JOIN messages m ON m.id = b.message_id
            JOIN conversations c ON c.id = m.conversation_id
            WHERE b.project_id = ? AND c.project_id = ?
            ORDER BY b.created_at DESC, m.id DESC LIMIT ?
            """,
            (project_id, project_id, min(100, max(1, limit))),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw = item.pop("tags_json", "[]")
        try:
            item["tags"] = json.loads(raw or "[]")
        except (ValueError, TypeError):
            item["tags"] = []
        result.append(item)
    return result
