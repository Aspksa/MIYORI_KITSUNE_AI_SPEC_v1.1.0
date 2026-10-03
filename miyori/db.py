from __future__ import annotations

import json
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

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_id, sha256),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(document_id, chunk_index),
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled')),
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                result_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS development_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
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


def add_document(
    project_id: int,
    filename: str,
    stored_path: str,
    mime_type: str | None,
    sha256: str,
    size_bytes: int,
    chunks: list[str],
) -> dict:
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id, project_id, filename, stored_path, mime_type, sha256, size_bytes, created_at
            FROM documents WHERE project_id = ? AND sha256 = ?
            """,
            (project_id, sha256),
        ).fetchone()
        if existing:
            return dict(existing)

        cur = conn.execute(
            """
            INSERT INTO documents(
                project_id, filename, stored_path, mime_type, sha256, size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, filename, stored_path, mime_type,
                sha256, size_bytes, utc_now(),
            ),
        )
        document_id = int(cur.lastrowid)

        for index, content in enumerate(chunks):
            conn.execute(
                """
                INSERT INTO document_chunks(document_id, chunk_index, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (document_id, index, content, utc_now()),
            )

        row = conn.execute(
            """
            SELECT id, project_id, filename, stored_path, mime_type, sha256, size_bytes, created_at
            FROM documents WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row)


def list_documents(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                d.id, d.filename, d.mime_type, d.sha256, d.size_bytes, d.created_at,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE d.project_id = ?
            GROUP BY d.id
            ORDER BY d.id DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def search_document_chunks(project_id: int, query: str, limit: int = 6) -> list[dict]:
    query_tokens = _memory_tokens(query)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id, c.chunk_index, c.content,
                d.id AS document_id, d.filename
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.project_id = ?
            ORDER BY c.id DESC
            LIMIT 1000
            """,
            (project_id,),
        ).fetchall()

    scored = []
    for recency, row in enumerate(rows):
        content_tokens = _memory_tokens(row["content"])
        overlap = len(query_tokens & content_tokens)
        exact_bonus = 4 if query.strip().lower() in row["content"].lower() else 0
        score = overlap * 10 + exact_bonus - min(recency, 100) * 0.005
        if overlap or exact_bonus:
            item = dict(row)
            item["score"] = round(score, 3)
            scored.append((score, item))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]



def create_task(project_id: int, task_type: str, payload: dict) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks(project_id, task_type, payload_json, status, created_at)
            VALUES (?, ?, ?, 'queued', ?)
            """,
            (project_id, task_type, json.dumps(payload, ensure_ascii=False), utc_now()),
        )
        row = conn.execute(
            """
            SELECT id, project_id, task_type, status, cancel_requested, created_at,
                   started_at, finished_at
            FROM tasks WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def list_tasks(project_id: int, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, task_type, status, cancel_requested, result_json,
                   created_at, started_at, finished_at
            FROM tasks
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["cancel_requested"] = bool(item["cancel_requested"])
        if item.get("result_json"):
            try:
                item["result"] = json.loads(item["result_json"])
            except json.JSONDecodeError:
                item["result"] = {"raw": item["result_json"]}
        else:
            item["result"] = None
        item.pop("result_json", None)
        result.append(item)
    return result


def claim_next_task() -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, task_type, payload_json
            FROM tasks
            WHERE status = 'queued'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None

        updated = conn.execute(
            """
            UPDATE tasks
            SET status = 'running', started_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (utc_now(), row["id"]),
        )
        if updated.rowcount != 1:
            return None

        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "task_type": row["task_type"],
            "payload": json.loads(row["payload_json"]),
        }


def request_task_cancel(project_id: int, task_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE tasks
            SET cancel_requested = 1,
                status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                finished_at = CASE WHEN status = 'queued' THEN ? ELSE finished_at END
            WHERE id = ? AND project_id = ? AND status IN ('queued','running')
            """,
            (utc_now(), task_id, project_id),
        )
        return cur.rowcount == 1


def is_task_cancel_requested(task_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT cancel_requested FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return bool(row and row["cancel_requested"])


def finish_task(task_id: int, status: str, result: dict) -> None:
    if status not in {"completed", "failed", "cancelled"}:
        raise ValueError("Недопустимый финальный статус задачи.")
    with connect() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = ?, result_json = ?, finished_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(result, ensure_ascii=False), utc_now(), task_id),
        )
        conn.execute(
            """
            INSERT INTO task_events(task_id, event_type, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, status, json.dumps(result, ensure_ascii=False), utc_now()),
        )


def record_task_event(task_id: int, event_type: str, details: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO task_events(task_id, event_type, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, event_type, details, utc_now()),
        )


def development_snapshot(project_id: int) -> dict:
    with connect() as conn:
        verified_facts = conn.execute(
            "SELECT COUNT(*) AS n FROM memory_facts WHERE project_id = ? AND status = 'verified'",
            (project_id,),
        ).fetchone()["n"]
        documents = conn.execute(
            "SELECT COUNT(*) AS n FROM documents WHERE project_id = ?",
            (project_id,),
        ).fetchone()["n"]
        document_chunks = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.project_id = ?
            """,
            (project_id,),
        ).fetchone()["n"]
        failed_tasks = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE project_id = ? AND status = 'failed'",
            (project_id,),
        ).fetchone()["n"]
        completed_tasks = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE project_id = ? AND status = 'completed'",
            (project_id,),
        ).fetchone()["n"]
        checks_passed = conn.execute(
            "SELECT COUNT(*) AS n FROM development_checks WHERE project_id = ? AND passed = 1",
            (project_id,),
        ).fetchone()["n"]
        checks_total = conn.execute(
            "SELECT COUNT(*) AS n FROM development_checks WHERE project_id = ?",
            (project_id,),
        ).fetchone()["n"]

    return {
        "verified_facts": int(verified_facts),
        "documents": int(documents),
        "document_chunks": int(document_chunks),
        "failed_tasks": int(failed_tasks),
        "completed_tasks": int(completed_tasks),
        "checks_passed": int(checks_passed),
        "checks_total": int(checks_total),
    }


def record_development_check(project_id: int, name: str, passed: bool, details: str) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO development_checks(project_id, name, passed, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, int(passed), details, utc_now()),
        )
        row = conn.execute(
            """
            SELECT id, name, passed, details, created_at
            FROM development_checks WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    item = dict(row)
    item["passed"] = bool(item["passed"])
    return item


def recent_development_checks(project_id: int, limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, passed, details, created_at
            FROM development_checks
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["passed"] = bool(item["passed"])
        result.append(item)
    return result
