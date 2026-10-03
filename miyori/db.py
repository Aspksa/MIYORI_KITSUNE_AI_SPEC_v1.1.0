from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from .config import settings


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT NOT NULL DEFAULT 'Новый разговор',
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS memory_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                conversation_id INTEGER,
                message_id INTEGER,
                locator TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                FOREIGN KEY(message_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS memory_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('candidate', 'verified', 'disputed', 'superseded')),
                source_id INTEGER,
                confidence REAL,
                verification_method TEXT,
                observed_at TEXT NOT NULL,
                valid_from TEXT,
                valid_until TEXT,
                supersedes_fact_id INTEGER,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(source_id) REFERENCES memory_sources(id),
                FOREIGN KEY(supersedes_fact_id) REFERENCES memory_facts(id)
            );
            """
        )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        }
        if "project_id" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN project_id INTEGER")

        row = conn.execute(
            "SELECT id FROM projects WHERE name = ?", ("Личное",)
        ).fetchone()
        if row:
            personal_id = int(row["id"])
        else:
            cur = conn.execute(
                "INSERT INTO projects(name, created_at) VALUES (?, ?)",
                ("Личное", utc_now()),
            )
            personal_id = int(cur.lastrowid)

        conn.execute(
            "UPDATE conversations SET project_id = ? WHERE project_id IS NULL",
            (personal_id,),
        )


def list_projects() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.created_at,
                COUNT(c.id) AS conversation_count
            FROM projects p
            LEFT JOIN conversations c ON c.project_id = p.id
            GROUP BY p.id
            ORDER BY CASE WHEN p.name = 'Личное' THEN 0 ELSE 1 END, p.name COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_project(name: str) -> dict:
    clean = name.strip()
    if not clean:
        raise ValueError("Название проекта пустое.")

    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO projects(name, created_at) VALUES (?, ?)",
                (clean, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Проект с таким названием уже существует.") from exc

        row = conn.execute(
            "SELECT id, name, created_at FROM projects WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def get_project(project_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None


def list_conversations(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.created_at,
                MAX(m.created_at) AS updated_at,
                COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.project_id = ?
            GROUP BY c.id
            ORDER BY COALESCE(MAX(m.created_at), c.created_at) DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id: int, project_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, title, created_at
            FROM conversations
            WHERE id = ? AND project_id = ?
            """,
            (conversation_id, project_id),
        ).fetchone()
    return dict(row) if row else None


def conversation_messages(conversation_id: int, project_id: int) -> list[dict]:
    if not get_conversation(conversation_id, project_id):
        return []

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def ensure_conversation(conversation_id: int | None, project_id: int) -> int:
    if conversation_id:
        conversation = get_conversation(conversation_id, project_id)
        if conversation:
            return int(conversation["id"])
        raise ValueError("Разговор не принадлежит выбранному проекту.")

    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations(project_id, title, created_at) VALUES (?, ?, ?)",
            (project_id, "Новый разговор", utc_now()),
        )
        return int(cur.lastrowid)


def add_message(conversation_id: int, role: str, content: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, utc_now()),
        )
        message_id = int(cur.lastrowid)

        if role == "user":
            row = conn.execute(
                "SELECT title FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row and row["title"] == "Новый разговор":
                title = content.strip().replace("\n", " ")
                if len(title) > 56:
                    title = title[:53].rstrip() + "..."
                conn.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title or "Новый разговор", conversation_id),
                )

        return message_id


def add_memory_fact(
    project_id: int,
    statement: str,
    status: str = "candidate",
    source_kind: str = "user_message",
    conversation_id: int | None = None,
    message_id: int | None = None,
    confidence: float | None = None,
    verification_method: str | None = None,
) -> dict:
    clean = statement.strip()
    if not clean:
        raise ValueError("Факт пустой.")
    if status not in {"candidate", "verified", "disputed", "superseded"}:
        raise ValueError("Недопустимый статус памяти.")

    with connect() as conn:
        duplicate = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method, observed_at
            FROM memory_facts
            WHERE project_id = ? AND lower(statement) = lower(?) AND status != 'superseded'
            ORDER BY id DESC LIMIT 1
            """,
            (project_id, clean),
        ).fetchone()
        if duplicate:
            return dict(duplicate)

        source_cur = conn.execute(
            """
            INSERT INTO memory_sources(project_id, kind, conversation_id, message_id, locator, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, source_kind, conversation_id, message_id, None, utc_now()),
        )
        source_id = int(source_cur.lastrowid)

        fact_cur = conn.execute(
            """
            INSERT INTO memory_facts(
                project_id, statement, status, source_id, confidence,
                verification_method, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, clean, status, source_id, confidence,
                verification_method, utc_now(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method, observed_at
            FROM memory_facts WHERE id = ?
            """,
            (fact_cur.lastrowid,),
        ).fetchone()
    return dict(row)


def list_memory_facts(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                f.id, f.statement, f.status, f.confidence, f.verification_method,
                f.observed_at, s.kind AS source_kind, s.conversation_id, s.message_id
            FROM memory_facts f
            LEFT JOIN memory_sources s ON s.id = f.source_id
            WHERE f.project_id = ?
            ORDER BY
                CASE f.status
                    WHEN 'verified' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'disputed' THEN 2
                    ELSE 3
                END,
                f.id DESC
            """,
            (project_id,),
        ).fetchall()
    facts = [dict(row) for row in rows]
    active = [
        fact for fact in facts
        if fact["status"] in {"candidate", "verified"}
    ]
    for fact in facts:
        fact["possible_conflict_ids"] = []

    for index, left in enumerate(active):
        left_tokens = _memory_tokens(left["statement"])
        if len(left_tokens) < 2:
            continue
        for right in active[index + 1:]:
            right_tokens = _memory_tokens(right["statement"])
            shared = left_tokens & right_tokens
            left_unique = left_tokens - right_tokens
            right_unique = right_tokens - left_tokens
            if len(shared) >= 2 and left_unique and right_unique:
                left["possible_conflict_ids"].append(right["id"])
                right["possible_conflict_ids"].append(left["id"])

    return facts


def update_memory_status(project_id: int, fact_id: int, status: str) -> dict | None:
    if status not in {"candidate", "verified", "disputed", "superseded"}:
        raise ValueError("Недопустимый статус памяти.")
    with connect() as conn:
        conn.execute(
            """
            UPDATE memory_facts
            SET status = ?,
                verification_method = CASE
                    WHEN ? = 'verified' THEN 'user_confirmed'
                    ELSE verification_method
                END
            WHERE id = ? AND project_id = ?
            """,
            (status, status, fact_id, project_id),
        )
        row = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method, observed_at
            FROM memory_facts WHERE id = ? AND project_id = ?
            """,
            (fact_id, project_id),
        ).fetchone()
    return dict(row) if row else None


def _memory_tokens(text: str) -> set[str]:
    stop = {
        "что", "это", "как", "для", "или", "мне", "мой", "моя", "мои",
        "про", "при", "под", "над", "без", "есть", "был", "была", "будет",
        "какой", "какая", "какие", "который", "когда", "где", "чем",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}", text.lower())
        if token not in stop
    }


def search_verified_memory(project_id: int, query: str, limit: int = 8) -> list[dict]:
    query_tokens = _memory_tokens(query)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, statement, observed_at
            FROM memory_facts
            WHERE project_id = ? AND status = 'verified'
            ORDER BY id DESC
            LIMIT 200
            """,
            (project_id,),
        ).fetchall()

    scored = []
    for recency, row in enumerate(rows):
        statement_tokens = _memory_tokens(row["statement"])
        overlap = len(query_tokens & statement_tokens)
        exact_bonus = 3 if query.strip().lower() in row["statement"].lower() else 0
        score = overlap * 10 + exact_bonus - min(recency, 50) * 0.02
        if overlap or exact_bonus:
            scored.append((score, dict(row)))

    if not scored:
        return [dict(row) for row in rows[: min(limit, 3)]]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def verified_memory_context(project_id: int, query: str, limit: int = 8) -> list[str]:
    return [
        row["statement"]
        for row in search_verified_memory(project_id, query, limit=limit)
    ]


def replace_memory_fact(
    project_id: int,
    fact_id: int,
    statement: str,
    source_kind: str = "user_correction",
) -> dict:
    clean = statement.strip()
    if not clean:
        raise ValueError("Новый факт пустой.")

    with connect() as conn:
        old = conn.execute(
            """
            SELECT id, status FROM memory_facts
            WHERE id = ? AND project_id = ?
            """,
            (fact_id, project_id),
        ).fetchone()
        if not old:
            raise ValueError("Исходный факт не найден.")

        now = utc_now()
        conn.execute(
            """
            UPDATE memory_facts
            SET status = 'superseded', valid_until = ?
            WHERE id = ? AND project_id = ?
            """,
            (now, fact_id, project_id),
        )

        source_cur = conn.execute(
            """
            INSERT INTO memory_sources(project_id, kind, locator, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, source_kind, f"replaces_fact:{fact_id}", now),
        )
        source_id = int(source_cur.lastrowid)

        fact_cur = conn.execute(
            """
            INSERT INTO memory_facts(
                project_id, statement, status, source_id,
                verification_method, observed_at, valid_from, supersedes_fact_id
            ) VALUES (?, ?, 'verified', ?, 'user_correction', ?, ?, ?)
            """,
            (project_id, clean, source_id, now, now, fact_id),
        )
        row = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method,
                   observed_at, valid_from, valid_until, supersedes_fact_id
            FROM memory_facts WHERE id = ?
            """,
            (fact_cur.lastrowid,),
        ).fetchone()
    return dict(row)


def maybe_capture_user_memory(
    project_id: int,
    conversation_id: int,
    message_id: int,
    content: str,
) -> dict | None:
    text = content.strip()
    lowered = text.lower()
    triggers = (
        "запомни ",
        "запомни:",
        "я предпочитаю ",
        "мне нравится ",
        "мне не нравится ",
        "мой любимый ",
        "моя любимая ",
        "для этого проекта ",
    )
    if not lowered.startswith(triggers):
        return None

    statement = text
    if lowered.startswith("запомни:"):
        statement = text.split(":", 1)[1].strip()
    elif lowered.startswith("запомни "):
        statement = text[8:].strip()

    if not statement:
        return None

    return add_memory_fact(
        project_id=project_id,
        statement=statement,
        status="candidate",
        source_kind="user_message",
        conversation_id=conversation_id,
        message_id=message_id,
        confidence=None,
        verification_method=None,
    )


def recent_messages(conversation_id: int, limit: int = 30) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]
