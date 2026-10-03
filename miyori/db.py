from __future__ import annotations

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


def add_message(conversation_id: int, role: str, content: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, utc_now()),
        )

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
