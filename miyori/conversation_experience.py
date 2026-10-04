from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings
from .db import add_memory_fact, connect, get_conversation, utc_now
from .rag import retrieve as rag_retrieve


_ALLOWED_REACTIONS = {"useful", "verify", "pin", "remember"}
_ALLOWED_ROUTES = {"new_chat", "saved", "knowledge", "documents", "tasks", "agent"}
_ALLOWED_REPEAT = {"none", "daily", "weekly"}
_WORDS = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{3,}")
_AUDIO_MIME = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}


def init_conversation_experience_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_topics(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(conversation_id,name)
            );
            CREATE TABLE IF NOT EXISTS chat_message_topics(
                topic_id INTEGER NOT NULL REFERENCES chat_topics(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                PRIMARY KEY(topic_id,message_id)
            );
            CREATE TABLE IF NOT EXISTS chat_message_tags(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(project_id,message_id,tag)
            );
            CREATE TABLE IF NOT EXISTS chat_message_pins(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                PRIMARY KEY(project_id,conversation_id,message_id)
            );
            CREATE TABLE IF NOT EXISTS chat_message_reactions(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                reaction TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(project_id,message_id,reaction)
            );
            CREATE TABLE IF NOT EXISTS chat_message_checklists(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                items_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id,message_id)
            );
            CREATE TABLE IF NOT EXISTS chat_message_routes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                destination TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_folders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_id,name)
            );
            CREATE TABLE IF NOT EXISTS chat_folder_conversations(
                folder_id INTEGER NOT NULL REFERENCES chat_folders(id) ON DELETE CASCADE,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                PRIMARY KEY(folder_id,conversation_id)
            );
            CREATE TABLE IF NOT EXISTS chat_read_state(
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                last_read_message_id INTEGER,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id,conversation_id)
            );
            CREATE TABLE IF NOT EXISTS chat_scheduled_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                repeat_mode TEXT NOT NULL DEFAULT 'none',
                auto_send INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'scheduled',
                created_at TEXT NOT NULL,
                dispatched_at TEXT
            );
            CREATE TABLE IF NOT EXISTS chat_voice_notes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                stored_path TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                duration_ms INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chat_topics_conversation
              ON chat_topics(project_id,conversation_id);
            CREATE INDEX IF NOT EXISTS idx_chat_tags_tag
              ON chat_message_tags(project_id,tag);
            CREATE INDEX IF NOT EXISTS idx_chat_routes_message
              ON chat_message_routes(project_id,message_id);
            CREATE INDEX IF NOT EXISTS idx_chat_schedule_due
              ON chat_scheduled_messages(project_id,status,scheduled_for);
            """
        )


def _message(project_id: int, conversation_id: int, message_id: int) -> dict:
    with connect() as db:
        row = db.execute(
            """
            SELECT m.id,m.role,m.content,m.created_at,m.conversation_id
            FROM messages m JOIN conversations c ON c.id=m.conversation_id
            WHERE c.project_id=? AND c.id=? AND m.id=?
            """,
            (project_id, conversation_id, message_id),
        ).fetchone()
    if not row:
        raise LookupError("Сообщение не найдено в этом проекте и разговоре.")
    return dict(row)


def reply_context(
    project_id: int,
    conversation_id: int | None,
    message_id: int | None,
    quoted_text: str = "",
) -> dict | None:
    if message_id is None:
        return None
    if conversation_id is None:
        raise ValueError("Ответ на сообщение требует существующий разговор.")
    row = _message(project_id, conversation_id, int(message_id))
    quote = " ".join(str(quoted_text or "").split())[:800]
    source = str(row["content"] or "")
    if quote and quote.casefold() not in source.casefold():
        raise ValueError("Выбранная цитата не принадлежит указанному сообщению.")
    return {
        "message_id": int(row["id"]),
        "role": str(row["role"]),
        "quote": quote or source[:800],
        "source_preview": source[:1200],
    }


def voice_note(project_id: int, voice_note_id: int | None) -> dict | None:
    if voice_note_id is None:
        return None
    init_conversation_experience_db()
    with connect() as db:
        row = db.execute(
            """
            SELECT id,mime_type,size_bytes,duration_ms,created_at
            FROM chat_voice_notes WHERE id=? AND project_id=?
            """,
            (voice_note_id, project_id),
        ).fetchone()
    if not row:
        raise ValueError("Голосовая заметка не найдена в текущем проекте.")
    return dict(row)


def create_voice_note(
    project_id: int,
    data: bytes,
    mime_type: str,
    duration_ms: int | None,
) -> dict:
    init_conversation_experience_db()
    mime = str(mime_type or "").split(";", 1)[0].strip().lower()
    suffix = _AUDIO_MIME.get(mime)
    if not suffix:
        raise ValueError("Неподдерживаемый формат голосовой заметки.")
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError("Голосовая заметка должна быть от 1 байта до 20 МБ.")
    root = Path(settings.data_dir) / "voice_notes" / str(project_id)
    root.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + suffix
    path = root / filename
    path.write_bytes(data)
    rel = str(path.relative_to(settings.data_dir)).replace("\\", "/")
    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO chat_voice_notes(
                project_id,stored_path,mime_type,size_bytes,duration_ms,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                project_id, rel, mime, len(data),
                max(0, int(duration_ms)) if duration_ms is not None else None,
                utc_now(),
            ),
        )
        note_id = int(cur.lastrowid)
    return {
        "id": note_id,
        "mime_type": mime,
        "size_bytes": len(data),
        "duration_ms": max(0, int(duration_ms)) if duration_ms is not None else None,
        "url": f"/api/projects/{project_id}/voice-notes/{note_id}",
    }


def voice_note_path(project_id: int, note_id: int) -> tuple[Path, str] | None:
    init_conversation_experience_db()
    with connect() as db:
        row = db.execute(
            "SELECT stored_path,mime_type FROM chat_voice_notes WHERE id=? AND project_id=?",
            (note_id, project_id),
        ).fetchone()
    if not row:
        return None
    path = (Path(settings.data_dir) / str(row["stored_path"])).resolve()
    root = Path(settings.data_dir).resolve()
    if root not in path.parents:
        return None
    return path, str(row["mime_type"])

def delete_voice_note(project_id: int, note_id: int) -> bool:
    init_conversation_experience_db()
    with connect() as db:
        row = db.execute(
            "SELECT stored_path FROM chat_voice_notes WHERE id=? AND project_id=?",
            (note_id, project_id),
        ).fetchone()
        if not row:
            return False
        path = (Path(settings.data_dir) / str(row["stored_path"])).resolve()
        root = Path(settings.data_dir).resolve()
        db.execute(
            "DELETE FROM chat_voice_notes WHERE id=? AND project_id=?",
            (note_id, project_id),
        )
    if root in path.parents:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return True



def create_topic(project_id: int, conversation_id: int, name: str) -> dict:
    init_conversation_experience_db()
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    clean = " ".join(str(name or "").split())[:80]
    if not clean:
        raise ValueError("Название темы пустое.")
    with connect() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO chat_topics(project_id,conversation_id,name,created_at)
            VALUES(?,?,?,?)
            """,
            (project_id, conversation_id, clean, utc_now()),
        )
        row = db.execute(
            "SELECT id,project_id,conversation_id,name,created_at FROM chat_topics "
            "WHERE project_id=? AND conversation_id=? AND name=?",
            (project_id, conversation_id, clean),
        ).fetchone()
    return dict(row)


def validate_topic(project_id: int, conversation_id: int, topic_id: int | None) -> int | None:
    if topic_id is None:
        return None
    init_conversation_experience_db()
    with connect() as db:
        row = db.execute(
            "SELECT id FROM chat_topics WHERE id=? AND project_id=? AND conversation_id=?",
            (int(topic_id), project_id, conversation_id),
        ).fetchone()
    if not row:
        raise ValueError("Тема не принадлежит текущему разговору.")
    return int(row["id"])


def assign_topic(project_id: int, conversation_id: int, message_id: int, topic_id: int | None) -> None:
    if topic_id is None:
        return
    _message(project_id, conversation_id, message_id)
    with connect() as db:
        topic = db.execute(
            "SELECT id FROM chat_topics WHERE id=? AND project_id=? AND conversation_id=?",
            (topic_id, project_id, conversation_id),
        ).fetchone()
        if not topic:
            raise ValueError("Тема не принадлежит текущему разговору.")
        db.execute(
            "INSERT OR IGNORE INTO chat_message_topics(topic_id,message_id) VALUES(?,?)",
            (topic_id, message_id),
        )


def set_tags(project_id: int, conversation_id: int, message_id: int, tags: list[str]) -> list[str]:
    _message(project_id, conversation_id, message_id)
    normalized = []
    for raw in tags[:12]:
        tag = re.sub(r"\s+", "-", str(raw).strip().lower()).strip("#-")[:32]
        if tag and tag not in normalized:
            normalized.append(tag)
    with connect() as db:
        db.execute(
            "DELETE FROM chat_message_tags WHERE project_id=? AND message_id=?",
            (project_id, message_id),
        )
        for tag in normalized:
            db.execute(
                """
                INSERT INTO chat_message_tags(project_id,message_id,tag,created_at)
                VALUES(?,?,?,?)
                """,
                (project_id, message_id, tag, utc_now()),
            )
    return normalized


def set_pin(project_id: int, conversation_id: int, message_id: int, pinned: bool) -> dict:
    _message(project_id, conversation_id, message_id)
    with connect() as db:
        if pinned:
            db.execute(
                """
                INSERT OR IGNORE INTO chat_message_pins(
                    project_id,conversation_id,message_id,created_at
                ) VALUES(?,?,?,?)
                """,
                (project_id, conversation_id, message_id, utc_now()),
            )
        else:
            db.execute(
                "DELETE FROM chat_message_pins WHERE project_id=? AND conversation_id=? AND message_id=?",
                (project_id, conversation_id, message_id),
            )
    return {"message_id": message_id, "pinned": bool(pinned)}


def set_reaction(
    project_id: int,
    conversation_id: int,
    message_id: int,
    reaction: str,
    enabled: bool,
) -> list[str]:
    _message(project_id, conversation_id, message_id)
    reaction = str(reaction)
    if reaction not in _ALLOWED_REACTIONS:
        raise ValueError("Недопустимая реакция.")
    with connect() as db:
        if enabled:
            db.execute(
                """
                INSERT OR IGNORE INTO chat_message_reactions(
                    project_id,message_id,reaction,created_at
                ) VALUES(?,?,?,?)
                """,
                (project_id, message_id, reaction, utc_now()),
            )
        else:
            db.execute(
                "DELETE FROM chat_message_reactions WHERE project_id=? AND message_id=? AND reaction=?",
                (project_id, message_id, reaction),
            )
        rows = db.execute(
            "SELECT reaction FROM chat_message_reactions WHERE project_id=? AND message_id=? ORDER BY reaction",
            (project_id, message_id),
        ).fetchall()
    return [str(row["reaction"]) for row in rows]


def save_checklist(
    project_id: int,
    conversation_id: int,
    message_id: int,
    items: list[dict],
) -> list[dict]:
    _message(project_id, conversation_id, message_id)
    clean: list[dict] = []
    for item in items[:30]:
        text = " ".join(str(item.get("text") or "").split())[:240]
        if not text:
            continue
        clean.append({"text": text, "done": bool(item.get("done", False))})
    if not clean:
        raise ValueError("Чек-лист пуст.")
    with connect() as db:
        db.execute(
            """
            INSERT INTO chat_message_checklists(project_id,message_id,items_json,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(project_id,message_id) DO UPDATE SET
              items_json=excluded.items_json, updated_at=excluded.updated_at
            """,
            (project_id, message_id, json.dumps(clean, ensure_ascii=False), utc_now()),
        )
    return clean


def create_folder(project_id: int, name: str) -> dict:
    init_conversation_experience_db()
    clean = " ".join(str(name or "").split())[:60]
    if not clean:
        raise ValueError("Название папки пустое.")
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO chat_folders(project_id,name,created_at) VALUES(?,?,?)",
            (project_id, clean, utc_now()),
        )
        row = db.execute(
            "SELECT id,name,created_at FROM chat_folders WHERE project_id=? AND name=?",
            (project_id, clean),
        ).fetchone()
    return dict(row)


def set_conversation_folder(
    project_id: int,
    conversation_id: int,
    folder_id: int,
    enabled: bool,
) -> None:
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    with connect() as db:
        folder = db.execute(
            "SELECT id FROM chat_folders WHERE id=? AND project_id=?",
            (folder_id, project_id),
        ).fetchone()
        if not folder:
            raise LookupError("Папка не найдена.")
        if enabled:
            db.execute(
                "INSERT OR IGNORE INTO chat_folder_conversations(folder_id,conversation_id) VALUES(?,?)",
                (folder_id, conversation_id),
            )
        else:
            db.execute(
                "DELETE FROM chat_folder_conversations WHERE folder_id=? AND conversation_id=?",
                (folder_id, conversation_id),
            )


def folder_snapshot(project_id: int) -> dict:
    init_conversation_experience_db()
    with connect() as db:
        custom = [
            dict(row) for row in db.execute(
                """
                SELECT f.id,f.name,COUNT(fc.conversation_id) AS conversation_count
                FROM chat_folders f
                LEFT JOIN chat_folder_conversations fc ON fc.folder_id=f.id
                WHERE f.project_id=? GROUP BY f.id ORDER BY f.name COLLATE NOCASE
                """,
                (project_id,),
            ).fetchall()
        ]
        counts = {
            "all": int(db.execute(
                "SELECT COUNT(*) n FROM conversations WHERE project_id=?", (project_id,)
            ).fetchone()["n"]),
            "pinned": int(db.execute(
                "SELECT COUNT(*) n FROM conversations WHERE project_id=? AND pinned=1", (project_id,)
            ).fetchone()["n"]),
            "saved": int(db.execute(
                """
                SELECT COUNT(DISTINCT m.conversation_id) n FROM message_bookmarks b
                JOIN messages m ON m.id=b.message_id WHERE b.project_id=?
                """, (project_id,)
            ).fetchone()["n"]),
            "tasks": int(db.execute(
                """
                SELECT COUNT(DISTINCT m.conversation_id) n FROM messages m
                JOIN conversations c ON c.id=m.conversation_id
                WHERE c.project_id=? AND json_valid(m.metadata_json)
                  AND json_extract(m.metadata_json,'$.task_goal') IS NOT NULL
                """, (project_id,)
            ).fetchone()["n"]),
            "unread": int(db.execute(
                """
                SELECT COUNT(*) n FROM conversations c
                WHERE c.project_id=? AND COALESCE(
                  (SELECT MAX(m.id) FROM messages m WHERE m.conversation_id=c.id),0
                ) > COALESCE(
                  (SELECT r.last_read_message_id FROM chat_read_state r
                   WHERE r.project_id=c.project_id AND r.conversation_id=c.id),0
                )
                """, (project_id,)
            ).fetchone()["n"]),
        }
    return {"system": counts, "custom": custom}


def filter_conversation_ids(project_id: int, folder: str) -> set[int] | None:
    folder = str(folder or "all")
    if folder == "all":
        return None
    with connect() as db:
        if folder == "pinned":
            rows = db.execute(
                "SELECT id FROM conversations WHERE project_id=? AND pinned=1",
                (project_id,),
            ).fetchall()
        elif folder == "saved":
            rows = db.execute(
                """
                SELECT DISTINCT m.conversation_id id FROM message_bookmarks b
                JOIN messages m ON m.id=b.message_id WHERE b.project_id=?
                """, (project_id,)
            ).fetchall()
        elif folder == "tasks":
            rows = db.execute(
                """
                SELECT DISTINCT m.conversation_id id FROM messages m
                JOIN conversations c ON c.id=m.conversation_id
                WHERE c.project_id=? AND json_valid(m.metadata_json)
                  AND json_extract(m.metadata_json,'$.task_goal') IS NOT NULL
                """, (project_id,)
            ).fetchall()
        elif folder == "unread":
            rows = db.execute(
                """
                SELECT c.id FROM conversations c WHERE c.project_id=? AND
                COALESCE((SELECT MAX(m.id) FROM messages m WHERE m.conversation_id=c.id),0) >
                COALESCE((SELECT r.last_read_message_id FROM chat_read_state r
                 WHERE r.project_id=c.project_id AND r.conversation_id=c.id),0)
                """, (project_id,)
            ).fetchall()
        elif folder.startswith("custom:"):
            try:
                folder_id = int(folder.split(":", 1)[1])
            except ValueError:
                return set()
            rows = db.execute(
                """
                SELECT fc.conversation_id id FROM chat_folder_conversations fc
                JOIN chat_folders f ON f.id=fc.folder_id
                WHERE f.project_id=? AND f.id=?
                """, (project_id, folder_id)
            ).fetchall()
        else:
            return set()
    return {int(row["id"]) for row in rows}


def mark_read(project_id: int, conversation_id: int, message_id: int | None) -> dict:
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    if message_id is not None:
        _message(project_id, conversation_id, message_id)
    with connect() as db:
        db.execute(
            """
            INSERT INTO chat_read_state(project_id,conversation_id,last_read_message_id,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(project_id,conversation_id) DO UPDATE SET
              last_read_message_id=MAX(
                COALESCE(chat_read_state.last_read_message_id,0),
                COALESCE(excluded.last_read_message_id,0)
              ),
              updated_at=excluded.updated_at
            """,
            (project_id, conversation_id, message_id, utc_now()),
        )
        row = db.execute(
            "SELECT last_read_message_id,updated_at FROM chat_read_state WHERE project_id=? AND conversation_id=?",
            (project_id, conversation_id),
        ).fetchone()
    return dict(row)


def route_message(
    project_id: int,
    conversation_id: int,
    message_id: int,
    destination: str,
    detail: dict | None = None,
) -> dict:
    msg = _message(project_id, conversation_id, message_id)
    if destination not in _ALLOWED_ROUTES:
        raise ValueError("Недопустимое направление сообщения.")
    payload = dict(detail or {})
    payload["source_role"] = msg["role"]
    payload["source_preview"] = str(msg["content"])[:600]
    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO chat_message_routes(
                project_id,conversation_id,message_id,destination,detail_json,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                project_id, conversation_id, message_id, destination,
                json.dumps(payload, ensure_ascii=False), utc_now(),
            ),
        )
    return {
        "id": int(cur.lastrowid),
        "message_id": message_id,
        "destination": destination,
        "detail": payload,
    }


def remember_message_candidate(
    project_id: int,
    conversation_id: int,
    message_id: int,
    statement: str,
) -> dict:
    msg = _message(project_id, conversation_id, message_id)
    clean = " ".join(str(statement or "").split())[:1000]
    if not clean:
        clean = str(msg["content"])[:1000].strip()
    if not clean:
        raise ValueError("Нечего сохранять в Memory.")
    return add_memory_fact(
        project_id=project_id,
        statement=clean,
        status="candidate",
        source_kind=f"{msg['role']}_message",
        conversation_id=conversation_id,
        message_id=message_id,
        confidence=None,
        verification_method=None,
        memory_scope="project",
        memory_kind="fact",
        salience=0.65,
    )


def topic_recent_messages(
    project_id: int,
    conversation_id: int,
    topic_id: int,
    limit: int = 30,
) -> list[dict[str, str]]:
    validate_topic(project_id, conversation_id, topic_id)
    with connect() as db:
        rows = db.execute(
            """
            SELECT m.role,m.content FROM messages m
            JOIN chat_message_topics mt ON mt.message_id=m.id
            WHERE m.conversation_id=? AND mt.topic_id=?
              AND m.role IN ('user','assistant')
            ORDER BY m.id DESC LIMIT ?
            """,
            (conversation_id, topic_id, max(1, min(60, limit))),
        ).fetchall()
    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]


def pinned_chat_context(
    project_id: int,
    conversation_id: int,
    limit: int = 4,
) -> list[dict]:
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    with connect() as db:
        rows = db.execute(
            """
            SELECT m.id,m.role,m.content,p.created_at
            FROM chat_message_pins p
            JOIN messages m ON m.id=p.message_id
            WHERE p.project_id=? AND p.conversation_id=?
            ORDER BY p.created_at DESC LIMIT ?
            """,
            (project_id, conversation_id, max(1, min(8, limit))),
        ).fetchall()
    return [
        {
            "message_id": int(row["id"]),
            "role": row["role"],
            "text": str(row["content"])[:1200],
        }
        for row in rows
    ]


def conversation_snapshot(project_id: int, conversation_id: int) -> dict:
    init_conversation_experience_db()
    if not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    with connect() as db:
        topics = [
            dict(row) for row in db.execute(
                "SELECT id,name,created_at FROM chat_topics WHERE project_id=? AND conversation_id=? ORDER BY id",
                (project_id, conversation_id),
            ).fetchall()
        ]
        pins = [
            dict(row) for row in db.execute(
                """
                SELECT p.message_id,m.role,substr(m.content,1,240) preview,p.created_at
                FROM chat_message_pins p JOIN messages m ON m.id=p.message_id
                WHERE p.project_id=? AND p.conversation_id=? ORDER BY p.created_at DESC
                """, (project_id, conversation_id)
            ).fetchall()
        ]
        tags: dict[str, list[str]] = {}
        for row in db.execute(
            """
            SELECT t.message_id,t.tag FROM chat_message_tags t
            JOIN messages m ON m.id=t.message_id
            WHERE t.project_id=? AND m.conversation_id=? ORDER BY t.tag
            """, (project_id, conversation_id)
        ).fetchall():
            tags.setdefault(str(row["message_id"]), []).append(str(row["tag"]))
        reactions: dict[str, list[str]] = {}
        for row in db.execute(
            """
            SELECT r.message_id,r.reaction FROM chat_message_reactions r
            JOIN messages m ON m.id=r.message_id
            WHERE r.project_id=? AND m.conversation_id=? ORDER BY r.reaction
            """, (project_id, conversation_id)
        ).fetchall():
            reactions.setdefault(str(row["message_id"]), []).append(str(row["reaction"]))
        checklists = {}
        for row in db.execute(
            """
            SELECT k.message_id,k.items_json,k.updated_at FROM chat_message_checklists k
            JOIN messages m ON m.id=k.message_id
            WHERE k.project_id=? AND m.conversation_id=?
            """, (project_id, conversation_id)
        ).fetchall():
            try:
                items = json.loads(row["items_json"])
            except (ValueError, TypeError):
                items = []
            checklists[str(row["message_id"])] = {
                "items": items,
                "updated_at": row["updated_at"],
            }
        topic_map: dict[str, list[int]] = {}
        for row in db.execute(
            """
            SELECT mt.message_id,mt.topic_id FROM chat_message_topics mt
            JOIN chat_topics t ON t.id=mt.topic_id
            WHERE t.project_id=? AND t.conversation_id=?
            """, (project_id, conversation_id)
        ).fetchall():
            topic_map.setdefault(str(row["message_id"]), []).append(int(row["topic_id"]))
        read = db.execute(
            "SELECT last_read_message_id,updated_at FROM chat_read_state WHERE project_id=? AND conversation_id=?",
            (project_id, conversation_id),
        ).fetchone()
    return {
        "topics": topics,
        "pins": pins,
        "tags": tags,
        "reactions": reactions,
        "checklists": checklists,
        "message_topics": topic_map,
        "read_state": dict(read) if read else {"last_read_message_id": None},
    }


def schedule_message(
    project_id: int,
    conversation_id: int | None,
    text: str,
    scheduled_for: str,
    repeat_mode: str,
    auto_send: bool,
) -> dict:
    init_conversation_experience_db()
    clean = str(text or "").strip()[:20000]
    if not clean:
        raise ValueError("Отложенный запрос пуст.")
    if conversation_id is not None and not get_conversation(conversation_id, project_id):
        raise LookupError("Разговор не найден.")
    if repeat_mode not in _ALLOWED_REPEAT:
        raise ValueError("Недопустимый режим повтора.")
    try:
        parsed = datetime.fromisoformat(str(scheduled_for).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Некорректное время отправки.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    when = parsed.astimezone(timezone.utc).isoformat()
    with connect() as db:
        cur = db.execute(
            """
            INSERT INTO chat_scheduled_messages(
                project_id,conversation_id,text,scheduled_for,repeat_mode,
                auto_send,status,created_at
            ) VALUES(?,?,?,?,?,?, 'scheduled',?)
            """,
            (
                project_id, conversation_id, clean, when, repeat_mode,
                int(bool(auto_send)), utc_now(),
            ),
        )
        sid = int(cur.lastrowid)
    return {
        "id": sid, "conversation_id": conversation_id, "text": clean,
        "scheduled_for": when, "repeat_mode": repeat_mode,
        "auto_send": bool(auto_send), "status": "scheduled",
    }


def due_schedules(project_id: int, limit: int = 20) -> list[dict]:
    init_conversation_experience_db()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        rows = db.execute(
            """
            SELECT id,conversation_id,text,scheduled_for,repeat_mode,auto_send,status
            FROM chat_scheduled_messages
            WHERE project_id=? AND status='scheduled' AND scheduled_for<=?
            ORDER BY scheduled_for,id LIMIT ?
            """,
            (project_id, now, max(1, min(50, limit))),
        ).fetchall()
    return [dict(row) | {"auto_send": bool(row["auto_send"])} for row in rows]


def complete_schedule(project_id: int, schedule_id: int) -> dict:
    init_conversation_experience_db()
    with connect() as db:
        row = db.execute(
            """
            SELECT * FROM chat_scheduled_messages
            WHERE id=? AND project_id=? AND status='scheduled'
            """, (schedule_id, project_id)
        ).fetchone()
        if not row:
            raise LookupError("Отложенный запрос не найден.")
        repeat_mode = str(row["repeat_mode"])
        next_time = None
        if repeat_mode in {"daily", "weekly"}:
            parsed = datetime.fromisoformat(
                str(row["scheduled_for"]).replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            delta = timedelta(days=1 if repeat_mode == "daily" else 7)
            next_time = (parsed.astimezone(timezone.utc) + delta).isoformat()
            db.execute(
                """
                UPDATE chat_scheduled_messages
                SET scheduled_for=?,dispatched_at=?,status='scheduled'
                WHERE id=? AND project_id=?
                """,
                (next_time, utc_now(), schedule_id, project_id),
            )
        else:
            db.execute(
                """
                UPDATE chat_scheduled_messages
                SET dispatched_at=?,status='sent'
                WHERE id=? AND project_id=?
                """, (utc_now(), schedule_id, project_id)
            )
        updated = db.execute(
            """
            SELECT id,conversation_id,text,scheduled_for,repeat_mode,auto_send,status,dispatched_at
            FROM chat_scheduled_messages WHERE id=? AND project_id=?
            """, (schedule_id, project_id)
        ).fetchone()
    result = dict(updated)
    result["auto_send"] = bool(result["auto_send"])
    return result

def smart_search(
    project_id: int,
    query: str,
    *,
    conversation_id: int | None = None,
    scope: str = "project",
    limit: int = 30,
) -> dict:
    clean = " ".join(str(query or "").split())[:240]
    if not clean:
        return {"mode": "empty", "semantic_embeddings": False, "matches": []}
    tokens = list(dict.fromkeys(t.casefold() for t in _WORDS.findall(clean)))[:10]
    params: list[object] = [project_id]
    where = ""
    if scope == "conversation" and conversation_id is not None:
        where = " AND c.id=?"
        params.append(conversation_id)
    elif scope == "saved":
        where = " AND EXISTS(SELECT 1 FROM message_bookmarks b WHERE b.project_id=c.project_id AND b.message_id=m.id)"
    with connect() as db:
        rows = db.execute(
            """
            SELECT m.id,m.conversation_id,m.role,m.content,m.created_at,c.title,
              EXISTS(SELECT 1 FROM message_bookmarks b
                     WHERE b.project_id=c.project_id AND b.message_id=m.id) AS saved,
              EXISTS(SELECT 1 FROM chat_message_pins p
                     WHERE p.project_id=c.project_id AND p.message_id=m.id) AS pinned
            FROM messages m JOIN conversations c ON c.id=m.conversation_id
            WHERE c.project_id=? AND m.role IN ('user','assistant')
            """ + where + " ORDER BY m.id DESC LIMIT 1200",
            params,
        ).fetchall()
        tag_rows = db.execute(
            "SELECT message_id,tag FROM chat_message_tags WHERE project_id=?",
            (project_id,),
        ).fetchall()
    tags: dict[int, list[str]] = {}
    for row in tag_rows:
        tags.setdefault(int(row["message_id"]), []).append(str(row["tag"]))
    ranked = []
    qfold = clean.casefold()
    for recency, row in enumerate(rows):
        item = dict(row)
        text = str(item["content"] or "")
        folded = text.casefold()
        overlap = sum(1 for token in tokens if token in folded)
        exact = 20 if qfold in folded else 0
        tag_bonus = sum(4 for tag in tags.get(int(item["id"]), []) if any(t in tag for t in tokens))
        score = exact + overlap * 7 + tag_bonus + (2 if item["saved"] else 0) + (2 if item["pinned"] else 0)
        score -= min(recency, 500) * 0.002
        if score <= 0:
            continue
        ranked.append((score, int(item["id"]), {
            "kind": "chat",
            "message_id": int(item["id"]),
            "conversation_id": int(item["conversation_id"]),
            "title": str(item["title"] or "Разговор"),
            "role": item["role"],
            "preview": text[:360],
            "created_at": item["created_at"],
            "tags": tags.get(int(item["id"]), []),
            "saved": bool(item["saved"]),
            "pinned": bool(item["pinned"]),
        }))
    ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
    matches = [item for _, _, item in ranked[:max(1, min(limit, 50))]]

    # Reuse existing RAG channels for document/memory/knowledge search.
    if scope in {"project", "all"}:
        context = rag_retrieve(project_id, clean, limit=8)
        for item in context.items:
            matches.append({
                "kind": item.source_type,
                "title": item.title,
                "preview": item.content[:360],
                "locator": item.locator,
                "score": item.score,
            })
        mode = f"chat_ranked_lexical+{context.retrieval_mode}"
    else:
        mode = "chat_ranked_lexical"
    return {
        "mode": mode,
        "semantic_embeddings": False,
        "note": "Embeddings для истории чата не настроены; поиск честно использует ranked lexical + существующий RAG.",
        "matches": matches[:max(1, min(limit, 50))],
    }
