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

            CREATE TABLE IF NOT EXISTS project_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                module_key TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_id, module_key),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS account_profile (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                owner_name TEXT NOT NULL DEFAULT '',
                miyori_address TEXT NOT NULL DEFAULT 'Господин',
                avatar_path TEXT,
                language TEXT NOT NULL DEFAULT 'ru-RU',
                timezone TEXT NOT NULL DEFAULT 'UTC',
                profile_kind TEXT NOT NULL DEFAULT 'personal',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS device_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_key TEXT NOT NULL UNIQUE,
                device_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                session_kind TEXT NOT NULL DEFAULT 'desktop',
                status TEXT NOT NULL DEFAULT 'active',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_preferences (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                communication_style TEXT NOT NULL DEFAULT 'balanced',
                detail_level TEXT NOT NULL DEFAULT 'normal',
                initiative_level TEXT NOT NULL DEFAULT 'medium',
                ask_before_assuming INTEGER NOT NULL DEFAULT 0,
                suggest_next_steps INTEGER NOT NULL DEFAULT 1,
                use_rag INTEGER NOT NULL DEFAULT 1,
                use_verified_memory INTEGER NOT NULL DEFAULT 1,
                show_uncertainty INTEGER NOT NULL DEFAULT 1,
                priority_mode TEXT NOT NULL DEFAULT 'accuracy',
                operating_mode TEXT NOT NULL DEFAULT 'personal',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                department TEXT NOT NULL DEFAULT '',
                position TEXT NOT NULL DEFAULT '',
                fuel_card_number TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                inn TEXT NOT NULL DEFAULT '',
                kpp TEXT NOT NULL DEFAULT '',
                legal_address TEXT NOT NULL DEFAULT '',
                contact_person TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                counterparty_id INTEGER,
                contract_number TEXT NOT NULL,
                contract_date TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(counterparty_id) REFERENCES counterparties(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                counterparty_id INTEGER,
                contract_id INTEGER,
                offer_number TEXT NOT NULL,
                issue_date TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL DEFAULT 0,
                terms TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(counterparty_id) REFERENCES counterparties(id) ON DELETE SET NULL,
                FOREIGN KEY(contract_id) REFERENCES contracts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS home_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL DEFAULT 'device',
                address TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'offline',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parental_control_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                child_name TEXT NOT NULL,
                device_name TEXT NOT NULL,
                daily_limit_minutes INTEGER NOT NULL DEFAULT 120,
                bedtime_start TEXT NOT NULL DEFAULT '21:00',
                bedtime_end TEXT NOT NULL DEFAULT '07:00',
                blocked_categories TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
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
                metadata_json TEXT,
                client_request_id TEXT,
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
                memory_scope TEXT NOT NULL DEFAULT 'project'
                    CHECK(memory_scope IN ('user','project')),
                memory_kind TEXT NOT NULL DEFAULT 'fact'
                    CHECK(memory_kind IN ('fact','preference','process','constraint')),
                salience REAL NOT NULL DEFAULT 0.5,
                observed_at TEXT NOT NULL,
                valid_from TEXT,
                valid_until TEXT,
                supersedes_fact_id INTEGER,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(source_id) REFERENCES memory_sources(id),
                FOREIGN KEY(supersedes_fact_id) REFERENCES memory_facts(id)
            );

            CREATE TABLE IF NOT EXISTS document_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                parent_id INTEGER,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                deleted_at TEXT,
                trash_path TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(parent_id) REFERENCES document_folders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                folder_id INTEGER,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                deleted_at TEXT,
                trash_path TEXT,
                UNIQUE(project_id, sha256),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(folder_id) REFERENCES document_folders(id) ON DELETE SET NULL
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

            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                conversation_id INTEGER,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                max_steps INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                tool_name TEXT,
                reason TEXT NOT NULL,
                arguments_json TEXT,
                result_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS permission_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','denied','executed','failed')),
                reason TEXT,
                result_json TEXT,
                workflow_id INTEGER,
                workflow_step_id INTEGER,
                tool_operation_id INTEGER,
                idempotency_key TEXT,
                preview_json TEXT,
                created_at TEXT NOT NULL,
                decided_at TEXT,
                executed_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS agent_workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                conversation_id INTEGER,
                agent_run_id INTEGER,
                request_key TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'running','waiting_permission','recovering',
                    'completed','failed','cancelled'
                )),
                route_json TEXT NOT NULL,
                conversation_context_json TEXT NOT NULL,
                planner_mode TEXT NOT NULL DEFAULT 'model',
                current_step INTEGER NOT NULL DEFAULT 0,
                max_steps INTEGER NOT NULL DEFAULT 5,
                pending_permission_id INTEGER,
                result_json TEXT,
                error_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                UNIQUE(project_id, request_key),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
                FOREIGN KEY(agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('tool','finish')),
                tool_name TEXT,
                reason TEXT NOT NULL,
                arguments_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,
                status TEXT NOT NULL CHECK(status IN (
                    'planned','running','waiting_permission','recovery_required',
                    'completed','failed','skipped','cancelled'
                )),
                permission_request_id INTEGER,
                idempotency_key TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                UNIQUE(workflow_id, step_index),
                UNIQUE(workflow_id, idempotency_key),
                FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tool_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                workflow_id INTEGER,
                workflow_step_id INTEGER,
                permission_request_id INTEGER,
                tool_name TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                preflight_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL CHECK(status IN (
                    'planned','running','verifying','recovery_required',
                    'executed','failed','cancelled'
                )),
                result_json TEXT,
                error_json TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                UNIQUE(project_id, idempotency_key),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE SET NULL,
                FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                conversation_id INTEGER,
                workflow_id INTEGER,
                actor TEXT NOT NULL CHECK(actor IN ('user','miyori','system')),
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
                FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS proactive_signal_state (
                project_id INTEGER NOT NULL,
                signal_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('dismissed','snoozed')),
                snoozed_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id, signal_key, fingerprint),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

                        CREATE INDEX IF NOT EXISTS idx_agent_workflows_project_status
                ON agent_workflows(project_id, status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow
                ON workflow_steps(workflow_id, step_index);
            CREATE INDEX IF NOT EXISTS idx_tool_operations_recovery
                ON tool_operations(project_id, status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_events_project
                ON audit_events(project_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_proactive_signal_state_project
                ON proactive_signal_state(project_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS hand_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                action TEXT NOT NULL,
                arguments_json TEXT,
                result_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            """
        )

        tool_operation_schema = conn.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'tool_operations'
            """
        ).fetchone()
        tool_operation_sql = (
            str(tool_operation_schema["sql"] or "") if tool_operation_schema else ""
        )
        if "'verifying'" not in tool_operation_sql:
            conn.execute(
                "ALTER TABLE tool_operations RENAME TO tool_operations_legacy_0046"
            )
            conn.execute(
                """
                CREATE TABLE tool_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    workflow_id INTEGER,
                    workflow_step_id INTEGER,
                    permission_request_id INTEGER,
                    tool_name TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    preflight_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL CHECK(status IN (
                        'planned','running','verifying','recovery_required',
                        'executed','failed','cancelled'
                    )),
                    result_json TEXT,
                    error_json TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    UNIQUE(project_id, idempotency_key),
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY(workflow_id) REFERENCES agent_workflows(id) ON DELETE SET NULL,
                    FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO tool_operations(
                    id, project_id, workflow_id, workflow_step_id,
                    permission_request_id, tool_name, idempotency_key,
                    arguments_json, preflight_json, status,
                    result_json, error_json, attempt_count,
                    created_at, updated_at, started_at, finished_at
                )
                SELECT
                    id, project_id, workflow_id, workflow_step_id,
                    permission_request_id, tool_name, idempotency_key,
                    arguments_json, preflight_json, status,
                    result_json, error_json, attempt_count,
                    created_at, updated_at, started_at, finished_at
                FROM tool_operations_legacy_0046
                """
            )
            conn.execute("DROP TABLE tool_operations_legacy_0046")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tool_operations_recovery
                ON tool_operations(project_id, status, id DESC)
                """
            )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        }
        if "project_id" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN project_id INTEGER")

        project_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "kind" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN kind TEXT NOT NULL DEFAULT 'home'")

        message_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "metadata_json" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT")
        if "client_request_id" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN client_request_id TEXT")
        conn.execute("DROP INDEX IF EXISTS idx_messages_client_request")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_client_request
            ON messages(client_request_id)
            WHERE client_request_id IS NOT NULL
            """
        )

        memory_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(memory_facts)").fetchall()
        }
        if "memory_scope" not in memory_columns:
            conn.execute(
                "ALTER TABLE memory_facts ADD COLUMN memory_scope TEXT NOT NULL DEFAULT 'project'"
            )
        if "memory_kind" not in memory_columns:
            conn.execute(
                "ALTER TABLE memory_facts ADD COLUMN memory_kind TEXT NOT NULL DEFAULT 'fact'"
            )
        if "salience" not in memory_columns:
            conn.execute(
                "ALTER TABLE memory_facts ADD COLUMN salience REAL NOT NULL DEFAULT 0.5"
            )

        permission_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(permission_requests)").fetchall()
        }
        if "workflow_id" not in permission_columns:
            conn.execute("ALTER TABLE permission_requests ADD COLUMN workflow_id INTEGER")
        if "workflow_step_id" not in permission_columns:
            conn.execute("ALTER TABLE permission_requests ADD COLUMN workflow_step_id INTEGER")
        if "tool_operation_id" not in permission_columns:
            conn.execute("ALTER TABLE permission_requests ADD COLUMN tool_operation_id INTEGER")
        if "idempotency_key" not in permission_columns:
            conn.execute("ALTER TABLE permission_requests ADD COLUMN idempotency_key TEXT")
        if "preview_json" not in permission_columns:
            conn.execute("ALTER TABLE permission_requests ADD COLUMN preview_json TEXT")

        document_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(documents)").fetchall()
        }
        if "folder_id" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN folder_id INTEGER")
        if "deleted_at" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN deleted_at TEXT")
        if "trash_path" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN trash_path TEXT")

        document_folder_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(document_folders)").fetchall()
        }
        if "deleted_at" not in document_folder_columns:
            conn.execute("ALTER TABLE document_folders ADD COLUMN deleted_at TEXT")
        if "trash_path" not in document_folder_columns:
            conn.execute("ALTER TABLE document_folders ADD COLUMN trash_path TEXT")

        conn.execute(
            "UPDATE projects SET kind = 'home' WHERE name = 'Личное'"
        )
        primavtodor = conn.execute(
            "SELECT id FROM projects WHERE name = ?",
            ('АО "Примавтодор"',),
        ).fetchone()
        if primavtodor:
            primavtodor_id = int(primavtodor["id"])
            conn.execute(
                "UPDATE projects SET kind = 'work' WHERE id = ?",
                (primavtodor_id,),
            )
        else:
            cur = conn.execute(
                "INSERT INTO projects(name, kind, created_at) VALUES (?, 'work', ?)",
                ('АО "Примавтодор"', utc_now()),
            )
            primavtodor_id = int(cur.lastrowid)

        for module_key, module_name in (
            ("timesheet", "Табель"),
            ("garage", "Гараж"),
            ("employees", "Сотрудники"),
            ("counterparties", "Контрагенты"),
            ("contracts", "Договоры"),
            ("invoice_offers", "Счёт-Оферта"),
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO project_modules(
                    project_id, module_key, name, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (primavtodor_id, module_key, module_name, utc_now()),
            )

        for folder_name in ("Контрагенты", "Договоры", "Счёт-Оферта"):
            existing_folder = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE project_id = ? AND parent_id IS NULL AND name = ?
                """,
                (primavtodor_id, folder_name),
            ).fetchone()
            if not existing_folder:
                conn.execute(
                    """
                    INSERT INTO document_folders(project_id, parent_id, name, created_at)
                    VALUES (?, NULL, ?, ?)
                    """,
                    (primavtodor_id, folder_name, utc_now()),
                )

        profile = conn.execute("SELECT id FROM account_profile WHERE id = 1").fetchone()
        if not profile:
            conn.execute(
                """
                INSERT INTO account_profile(
                    id, owner_name, miyori_address, avatar_path,
                    language, timezone, profile_kind, updated_at
                ) VALUES (1, '', 'Господин', NULL, 'ru-RU', 'UTC', 'personal', ?)
                """,
                (utc_now(),),
            )

        ai_pref = conn.execute("SELECT id FROM ai_preferences WHERE id = 1").fetchone()
        if not ai_pref:
            conn.execute(
                """
                INSERT INTO ai_preferences(
                    id, communication_style, detail_level, initiative_level,
                    ask_before_assuming, suggest_next_steps, use_rag,
                    use_verified_memory, show_uncertainty, priority_mode,
                    operating_mode, updated_at
                ) VALUES (1, 'balanced', 'normal', 'medium', 0, 1, 1, 1, 1, 'accuracy', 'personal', ?)
                """,
                (utc_now(),),
            )

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

        for module_key, module_name in (
            ("home_network", "Домашняя сеть"),
            ("parental_control", "Детский контроль Miyori"),
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO project_modules(
                    project_id, module_key, name, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (personal_id, module_key, module_name, utc_now()),
            )

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
                p.kind,
                p.created_at,
                COUNT(c.id) AS conversation_count
            FROM projects p
            LEFT JOIN conversations c ON c.project_id = p.id
            GROUP BY p.id
            ORDER BY CASE WHEN p.name = 'Личное' THEN 0 ELSE 1 END, p.name COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_account_profile() -> dict:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, owner_name, miyori_address, avatar_path,
                   language, timezone, profile_kind, updated_at
            FROM account_profile WHERE id = 1
            """
        ).fetchone()
    return dict(row) if row else {}


def update_account_profile(
    *,
    owner_name: str,
    miyori_address: str,
    language: str,
    timezone_name: str,
    profile_kind: str,
) -> dict:
    if profile_kind not in {"personal", "work"}:
        raise ValueError("Недопустимый основной профиль.")
    clean_owner = " ".join(owner_name.strip().split())[:120]
    clean_address = " ".join(miyori_address.strip().split())[:80] or "Господин"
    clean_language = language.strip()[:20] or "ru-RU"
    clean_timezone = timezone_name.strip()[:80] or "UTC"

    with connect() as conn:
        conn.execute(
            """
            UPDATE account_profile
            SET owner_name = ?, miyori_address = ?, language = ?,
                timezone = ?, profile_kind = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                clean_owner, clean_address, clean_language,
                clean_timezone, profile_kind, utc_now(),
            ),
        )
    return get_account_profile()


def update_account_avatar(avatar_path: str | None) -> dict:
    with connect() as conn:
        conn.execute(
            "UPDATE account_profile SET avatar_path = ?, updated_at = ? WHERE id = 1",
            (avatar_path, utc_now()),
        )
    return get_account_profile()


def upsert_device_session(
    *,
    device_key: str,
    device_name: str,
    platform_name: str,
    session_kind: str = "desktop",
) -> dict:
    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM device_sessions WHERE device_key = ?",
            (device_key,),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE device_sessions
                SET device_name = ?, platform = ?, session_kind = ?,
                    status = 'active', last_seen_at = ?
                WHERE device_key = ?
                """,
                (device_name, platform_name, session_kind, now, device_key),
            )
        else:
            conn.execute(
                """
                INSERT INTO device_sessions(
                    device_key, device_name, platform, session_kind,
                    status, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (device_key, device_name, platform_name, session_kind, now, now),
            )
        result = conn.execute(
            """
            SELECT id, device_key, device_name, platform, session_kind,
                   status, first_seen_at, last_seen_at
            FROM device_sessions WHERE device_key = ?
            """,
            (device_key,),
        ).fetchone()
    return dict(result)


def list_device_sessions() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, device_key, device_name, platform, session_kind,
                   status, first_seen_at, last_seen_at
            FROM device_sessions
            ORDER BY status = 'active' DESC, last_seen_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def disconnect_device_session(session_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE device_sessions
            SET status = 'disconnected', last_seen_at = ?
            WHERE id = ?
            """,
            (utc_now(), session_id),
        )
    return cur.rowcount == 1


def get_ai_preferences() -> dict:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, communication_style, detail_level, initiative_level,
                   ask_before_assuming, suggest_next_steps, use_rag,
                   use_verified_memory, show_uncertainty, priority_mode,
                   operating_mode, updated_at
            FROM ai_preferences WHERE id = 1
            """
        ).fetchone()
    return dict(row) if row else {}


def update_ai_preferences(
    *,
    communication_style: str,
    detail_level: str,
    initiative_level: str,
    ask_before_assuming: bool,
    suggest_next_steps: bool,
    use_rag: bool,
    use_verified_memory: bool,
    show_uncertainty: bool,
    priority_mode: str,
    operating_mode: str,
) -> dict:
    if communication_style not in {"balanced", "warm", "business", "minimal"}:
        raise ValueError("Недопустимый стиль общения.")
    if detail_level not in {"short", "normal", "detailed"}:
        raise ValueError("Недопустимый уровень подробности.")
    if initiative_level not in {"low", "medium", "high"}:
        raise ValueError("Недопустимый уровень инициативности.")
    if priority_mode not in {"accuracy", "balanced", "speed"}:
        raise ValueError("Недопустимый приоритет.")
    if operating_mode not in {"personal", "work", "analyst", "research", "developer"}:
        raise ValueError("Недопустимый режим Miyori.")

    with connect() as conn:
        conn.execute(
            """
            UPDATE ai_preferences
            SET communication_style = ?, detail_level = ?, initiative_level = ?,
                ask_before_assuming = ?, suggest_next_steps = ?, use_rag = ?,
                use_verified_memory = ?, show_uncertainty = ?,
                priority_mode = ?, operating_mode = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                communication_style, detail_level, initiative_level,
                int(ask_before_assuming), int(suggest_next_steps), int(use_rag),
                int(use_verified_memory), int(show_uncertainty),
                priority_mode, operating_mode, utc_now(),
            ),
        )
    return get_ai_preferences()


def list_employees(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, full_name, department, position,
                   fuel_card_number, created_at, updated_at
            FROM employees
            WHERE project_id = ?
            ORDER BY full_name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_employee(
    project_id: int,
    *,
    full_name: str,
    department: str,
    position: str,
    fuel_card_number: str,
) -> dict:
    clean_name = " ".join(full_name.strip().split())
    if not clean_name:
        raise ValueError("ФИО сотрудника обязательно.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO employees(
                project_id, full_name, department, position,
                fuel_card_number, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, clean_name, department.strip(), position.strip(),
                fuel_card_number.strip(), now, now,
            ),
        )
        row = conn.execute(
            """
            SELECT id, project_id, full_name, department, position,
                   fuel_card_number, created_at, updated_at
            FROM employees WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def update_employee(
    project_id: int,
    employee_id: int,
    *,
    full_name: str,
    department: str,
    position: str,
    fuel_card_number: str,
) -> dict | None:
    clean_name = " ".join(full_name.strip().split())
    if not clean_name:
        raise ValueError("ФИО сотрудника обязательно.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE employees
            SET full_name = ?, department = ?, position = ?,
                fuel_card_number = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                clean_name, department.strip(), position.strip(),
                fuel_card_number.strip(), utc_now(), employee_id, project_id,
            ),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute(
            """
            SELECT id, project_id, full_name, department, position,
                   fuel_card_number, created_at, updated_at
            FROM employees WHERE id = ?
            """,
            (employee_id,),
        ).fetchone()
    return dict(row)


def delete_employee(project_id: int, employee_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM employees WHERE id = ? AND project_id = ?",
            (employee_id, project_id),
        )
    return cur.rowcount == 1


def find_document_folder(project_id: int, name: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at
            FROM document_folders
            WHERE project_id = ? AND parent_id IS NULL AND name = ?
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (project_id, name),
        ).fetchone()
    return dict(row) if row else None


def list_counterparties(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, name, inn, kpp, legal_address,
                   contact_person, phone, email, created_at, updated_at
            FROM counterparties
            WHERE project_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_counterparty(project_id: int, **values) -> dict:
    name = " ".join(str(values.get("name", "")).strip().split())
    if not name:
        raise ValueError("Название контрагента обязательно.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO counterparties(
                project_id, name, inn, kpp, legal_address,
                contact_person, phone, email, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, name, str(values.get("inn", "")).strip(),
                str(values.get("kpp", "")).strip(),
                str(values.get("legal_address", "")).strip(),
                str(values.get("contact_person", "")).strip(),
                str(values.get("phone", "")).strip(),
                str(values.get("email", "")).strip(), now, now,
            ),
        )
        row = conn.execute("SELECT * FROM counterparties WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_counterparty(project_id: int, item_id: int, **values) -> dict | None:
    name = " ".join(str(values.get("name", "")).strip().split())
    if not name:
        raise ValueError("Название контрагента обязательно.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE counterparties
            SET name=?, inn=?, kpp=?, legal_address=?, contact_person=?,
                phone=?, email=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                name, str(values.get("inn", "")).strip(), str(values.get("kpp", "")).strip(),
                str(values.get("legal_address", "")).strip(),
                str(values.get("contact_person", "")).strip(),
                str(values.get("phone", "")).strip(), str(values.get("email", "")).strip(),
                utc_now(), item_id, project_id,
            ),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute("SELECT * FROM counterparties WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def delete_counterparty(project_id: int, item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM counterparties WHERE id=? AND project_id=?", (item_id, project_id))
    return cur.rowcount == 1


def list_contracts(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, p.name AS counterparty_name
            FROM contracts c
            LEFT JOIN counterparties p ON p.id = c.counterparty_id
            WHERE c.project_id = ?
            ORDER BY c.contract_date DESC, c.id DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_contract(project_id: int, **values) -> dict:
    number = str(values.get("contract_number", "")).strip()
    if not number:
        raise ValueError("Номер договора обязателен.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO contracts(
                project_id, counterparty_id, contract_number, contract_date,
                subject, amount, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, values.get("counterparty_id"), number,
                str(values.get("contract_date", "")).strip(),
                str(values.get("subject", "")).strip(),
                float(values.get("amount") or 0),
                str(values.get("status", "draft")).strip() or "draft", now, now,
            ),
        )
        row = conn.execute("SELECT * FROM contracts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_contract(project_id: int, item_id: int, **values) -> dict | None:
    number = str(values.get("contract_number", "")).strip()
    if not number:
        raise ValueError("Номер договора обязателен.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE contracts SET counterparty_id=?, contract_number=?, contract_date=?,
                subject=?, amount=?, status=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                values.get("counterparty_id"), number,
                str(values.get("contract_date", "")).strip(),
                str(values.get("subject", "")).strip(), float(values.get("amount") or 0),
                str(values.get("status", "draft")).strip() or "draft",
                utc_now(), item_id, project_id,
            ),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute("SELECT * FROM contracts WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def delete_contract(project_id: int, item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM contracts WHERE id=? AND project_id=?", (item_id, project_id))
    return cur.rowcount == 1


def list_invoice_offers(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT o.*, p.name AS counterparty_name, c.contract_number
            FROM invoice_offers o
            LEFT JOIN counterparties p ON p.id = o.counterparty_id
            LEFT JOIN contracts c ON c.id = o.contract_id
            WHERE o.project_id = ?
            ORDER BY o.issue_date DESC, o.id DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_invoice_offer(project_id: int, **values) -> dict:
    number = str(values.get("offer_number", "")).strip()
    if not number:
        raise ValueError("Номер счёта-оферты обязателен.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoice_offers(
                project_id, counterparty_id, contract_id, offer_number,
                issue_date, amount, terms, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, values.get("counterparty_id"), values.get("contract_id"),
                number, str(values.get("issue_date", "")).strip(),
                float(values.get("amount") or 0), str(values.get("terms", "")).strip(),
                str(values.get("status", "draft")).strip() or "draft", now, now,
            ),
        )
        row = conn.execute("SELECT * FROM invoice_offers WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_invoice_offer(project_id: int, item_id: int, **values) -> dict | None:
    number = str(values.get("offer_number", "")).strip()
    if not number:
        raise ValueError("Номер счёта-оферты обязателен.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE invoice_offers
            SET counterparty_id=?, contract_id=?, offer_number=?, issue_date=?,
                amount=?, terms=?, status=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                values.get("counterparty_id"), values.get("contract_id"), number,
                str(values.get("issue_date", "")).strip(), float(values.get("amount") or 0),
                str(values.get("terms", "")).strip(),
                str(values.get("status", "draft")).strip() or "draft",
                utc_now(), item_id, project_id,
            ),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute("SELECT * FROM invoice_offers WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def delete_invoice_offer(project_id: int, item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM invoice_offers WHERE id=? AND project_id=?", (item_id, project_id))
    return cur.rowcount == 1


def list_home_devices(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, name, device_type, address, status, notes,
                   created_at, updated_at
            FROM home_devices WHERE project_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_home_device(project_id: int, **values) -> dict:
    name = " ".join(str(values.get("name", "")).strip().split())
    if not name:
        raise ValueError("Название устройства обязательно.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO home_devices(
                project_id, name, device_type, address, status, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, name, str(values.get("device_type", "device")).strip() or "device",
                str(values.get("address", "")).strip(),
                str(values.get("status", "offline")).strip() or "offline",
                str(values.get("notes", "")).strip(), now, now,
            ),
        )
        row = conn.execute("SELECT * FROM home_devices WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_home_device(project_id: int, item_id: int, **values) -> dict | None:
    name = " ".join(str(values.get("name", "")).strip().split())
    if not name:
        raise ValueError("Название устройства обязательно.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE home_devices SET name=?, device_type=?, address=?, status=?,
                notes=?, updated_at=? WHERE id=? AND project_id=?
            """,
            (
                name, str(values.get("device_type", "device")).strip() or "device",
                str(values.get("address", "")).strip(),
                str(values.get("status", "offline")).strip() or "offline",
                str(values.get("notes", "")).strip(), utc_now(), item_id, project_id,
            ),
        )
        if cur.rowcount != 1: return None
        row = conn.execute("SELECT * FROM home_devices WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def delete_home_device(project_id: int, item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM home_devices WHERE id=? AND project_id=?", (item_id, project_id))
    return cur.rowcount == 1


def list_parental_profiles(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, child_name, device_name, daily_limit_minutes,
                   bedtime_start, bedtime_end, blocked_categories, status,
                   created_at, updated_at
            FROM parental_control_profiles WHERE project_id = ?
            ORDER BY child_name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_parental_profile(project_id: int, **values) -> dict:
    child = " ".join(str(values.get("child_name", "")).strip().split())
    device = " ".join(str(values.get("device_name", "")).strip().split())
    if not child or not device:
        raise ValueError("Укажите ребёнка и устройство.")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO parental_control_profiles(
                project_id, child_name, device_name, daily_limit_minutes,
                bedtime_start, bedtime_end, blocked_categories, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, child, device, max(0, int(values.get("daily_limit_minutes") or 0)),
                str(values.get("bedtime_start", "21:00")).strip() or "21:00",
                str(values.get("bedtime_end", "07:00")).strip() or "07:00",
                str(values.get("blocked_categories", "")).strip(),
                str(values.get("status", "draft")).strip() or "draft", now, now,
            ),
        )
        row = conn.execute("SELECT * FROM parental_control_profiles WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_parental_profile(project_id: int, item_id: int, **values) -> dict | None:
    child = " ".join(str(values.get("child_name", "")).strip().split())
    device = " ".join(str(values.get("device_name", "")).strip().split())
    if not child or not device:
        raise ValueError("Укажите ребёнка и устройство.")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE parental_control_profiles
            SET child_name=?, device_name=?, daily_limit_minutes=?,
                bedtime_start=?, bedtime_end=?, blocked_categories=?,
                status=?, updated_at=? WHERE id=? AND project_id=?
            """,
            (
                child, device, max(0, int(values.get("daily_limit_minutes") or 0)),
                str(values.get("bedtime_start", "21:00")).strip() or "21:00",
                str(values.get("bedtime_end", "07:00")).strip() or "07:00",
                str(values.get("blocked_categories", "")).strip(),
                str(values.get("status", "draft")).strip() or "draft",
                utc_now(), item_id, project_id,
            ),
        )
        if cur.rowcount != 1: return None
        row = conn.execute("SELECT * FROM parental_control_profiles WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def delete_parental_profile(project_id: int, item_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM parental_control_profiles WHERE id=? AND project_id=?", (item_id, project_id))
    return cur.rowcount == 1


def create_project(name: str, kind: str = "home") -> dict:
    clean = name.strip()
    if kind not in {"home", "work"}:
        raise ValueError("Недопустимый тип проекта.")
    if not clean:
        raise ValueError("Название проекта пустое.")

    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO projects(name, kind, created_at) VALUES (?, ?, ?)",
                (clean, kind, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Проект с таким названием уже существует.") from exc

        row = conn.execute(
            "SELECT id, name, kind, created_at FROM projects WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def get_project(project_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, kind, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None


def list_project_modules(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, module_key, name, created_at
            FROM project_modules
            WHERE project_id = ?
            ORDER BY
                CASE module_key
                    WHEN 'timesheet' THEN 1
                    WHEN 'garage' THEN 2
                    WHEN 'employees' THEN 3
                    WHEN 'counterparties' THEN 4
                    WHEN 'contracts' THEN 5
                    WHEN 'invoice_offers' THEN 6
                    ELSE 99
                END,
                name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


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
            SELECT id, role, content, metadata_json, client_request_id, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw_metadata = item.pop("metadata_json", None)
        if raw_metadata:
            try:
                item["metadata"] = json.loads(raw_metadata)
            except json.JSONDecodeError:
                item["metadata"] = {}
        else:
            item["metadata"] = {}
        result.append(item)
    return result


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


def add_message(
    conversation_id: int,
    role: str,
    content: str,
    metadata: dict | None = None,
    client_request_id: str | None = None,
) -> int:
    with connect() as conn:
        if client_request_id:
            existing = conn.execute(
                """
                SELECT id FROM messages
                WHERE client_request_id = ?
                LIMIT 1
                """,
                (client_request_id,),
            ).fetchone()
            if existing:
                return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO messages(
                conversation_id, role, content, metadata_json,
                client_request_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(metadata or {}, ensure_ascii=False),
                client_request_id,
                utc_now(),
            ),
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



def get_message_by_client_request_id(
    project_id: int,
    client_request_id: str,
) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT m.id, m.conversation_id, m.role, m.content, m.metadata_json,
                   m.client_request_id, m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.project_id = ? AND m.client_request_id = ?
            LIMIT 1
            """,
            (project_id, client_request_id),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["metadata"] = _loads_json(item.pop("metadata_json", None), {})
    return item


def add_memory_fact(
    project_id: int,
    statement: str,
    status: str = "candidate",
    source_kind: str = "user_message",
    conversation_id: int | None = None,
    message_id: int | None = None,
    confidence: float | None = None,
    verification_method: str | None = None,
    memory_scope: str = "project",
    memory_kind: str = "fact",
    salience: float = 0.5,
) -> dict:
    clean = statement.strip()
    if not clean:
        raise ValueError("Факт пустой.")
    if status not in {"candidate", "verified", "disputed", "superseded"}:
        raise ValueError("Недопустимый статус памяти.")
    if memory_scope not in {"user", "project"}:
        raise ValueError("Недопустимый scope памяти.")
    if memory_kind not in {"fact", "preference", "process", "constraint"}:
        raise ValueError("Недопустимый тип памяти.")
    salience = max(0.0, min(1.0, float(salience)))

    with connect() as conn:
        duplicate = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method,
                   memory_scope, memory_kind, salience, observed_at
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
                verification_method, memory_scope, memory_kind, salience, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, clean, status, source_id, confidence,
                verification_method, memory_scope, memory_kind, salience, utc_now(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method,
                   memory_scope, memory_kind, salience, observed_at
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
                f.id, f.project_id, f.statement, f.status, f.confidence, f.verification_method,
                f.memory_scope, f.memory_kind, f.salience,
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
            SELECT id, statement, status, confidence, verification_method,
                   memory_scope, memory_kind, salience, observed_at
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
        "пользователь", "пользователя", "проект", "проекта",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}", text.lower())
        if token not in stop
    }


def search_verified_memory(
    project_id: int,
    query: str,
    limit: int = 8,
    *,
    include_user: bool = True,
    include_project: bool = True,
) -> list[dict]:
    query_tokens = _memory_tokens(query)
    visibility: list[str] = []
    params: list[object] = []

    if include_user:
        visibility.append("f.memory_scope = 'user'")
    if include_project:
        visibility.append("(f.memory_scope = 'project' AND f.project_id = ?)")
        params.append(project_id)
    if not visibility:
        return []

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT f.id, f.project_id, f.statement, f.observed_at,
                   f.memory_scope, f.memory_kind, f.salience,
                   f.confidence, f.verification_method
            FROM memory_facts f
            WHERE f.status = 'verified'
              AND ({' OR '.join(visibility)})
            ORDER BY f.id DESC
            LIMIT 300
            """,
            params,
        ).fetchall()

    scored: list[tuple[float, dict]] = []
    seen_statements: set[str] = set()
    for recency, row in enumerate(rows):
        item = dict(row)
        normalized = " ".join(item["statement"].lower().split())
        if normalized in seen_statements:
            continue
        seen_statements.add(normalized)

        statement_tokens = _memory_tokens(item["statement"])
        overlap = len(query_tokens & statement_tokens)
        exact_bonus = 3 if query.strip().lower() in item["statement"].lower() else 0
        scope_bonus = 0.7 if item["memory_scope"] == "project" else 0.4
        kind_bonus = 0.6 if item["memory_kind"] == "preference" else 0.0
        score = (
            overlap * 10
            + exact_bonus
            + scope_bonus
            + kind_bonus
            + float(item.get("salience") or 0.5)
            - min(recency, 80) * 0.015
        )
        if overlap or exact_bonus:
            scored.append((score, item))

    if not scored:
        # No semantic match: only return a tiny amount of high-salience user
        # preference memory. Never flood the prompt with unrelated project facts.
        fallback = [
            dict(row) for row in rows
            if row["memory_scope"] == "user"
            and row["memory_kind"] == "preference"
            and float(row["salience"] or 0) >= 0.7
        ]
        return fallback[: min(limit, 2)]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def verified_memory_context(
    project_id: int,
    query: str,
    limit: int = 8,
    *,
    include_user: bool = True,
    include_project: bool = True,
) -> list[dict]:
    return search_verified_memory(
        project_id,
        query,
        limit=limit,
        include_user=include_user,
        include_project=include_project,
    )


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
            SELECT id, status, memory_scope, memory_kind, salience FROM memory_facts
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
                verification_method, memory_scope, memory_kind, salience,
                observed_at, valid_from, supersedes_fact_id
            ) VALUES (?, ?, 'verified', ?, 'user_correction', ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, clean, source_id,
                old["memory_scope"], old["memory_kind"], old["salience"],
                now, now, fact_id,
            ),
        )
        row = conn.execute(
            """
            SELECT id, statement, status, confidence, verification_method,
                   memory_scope, memory_kind, salience,
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
    """Capture only explicit/stable memory; ordinary chat is not long-term memory."""
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
        "в этом проекте ",
    )
    if not lowered.startswith(triggers):
        return None

    statement = text
    explicit_remember = lowered.startswith(("запомни ", "запомни:"))
    if lowered.startswith("запомни:"):
        statement = text.split(":", 1)[1].strip()
    elif lowered.startswith("запомни "):
        statement = text[8:].strip()

    if not statement:
        return None

    preference_markers = (
        "я предпочитаю", "мне нравится", "мне не нравится",
        "мой любимый", "моя любимая",
    )
    project_markers = ("для этого проекта", "в этом проекте")

    memory_scope = (
        "project"
        if lowered.startswith(project_markers)
        else "user"
        if lowered.startswith(preference_markers) or explicit_remember
        else "project"
    )
    memory_kind = (
        "preference"
        if lowered.startswith(preference_markers)
        else "constraint"
        if any(marker in lowered for marker in ("всегда ", "никогда ", "обязательно "))
        else "process"
        if any(marker in lowered for marker in ("процесс", "порядок работы", "сначала "))
        else "fact"
    )

    user_authoritative = memory_scope == "user" and (
        memory_kind == "preference" or explicit_remember
    )
    return add_memory_fact(
        project_id=project_id,
        statement=statement,
        status="verified" if user_authoritative else "candidate",
        source_kind="user_message",
        conversation_id=conversation_id,
        message_id=message_id,
        confidence=1.0 if user_authoritative else None,
        verification_method="direct_user" if user_authoritative else None,
        memory_scope=memory_scope,
        memory_kind=memory_kind,
        salience=0.9 if explicit_remember else 0.75 if memory_kind == "preference" else 0.6,
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


def create_document_folder(
    project_id: int,
    name: str,
    parent_id: int | None = None,
) -> dict:
    clean = " ".join(name.strip().split())
    if not clean:
        raise ValueError("Название папки пустое.")
    if len(clean) > 120:
        raise ValueError("Название папки слишком длинное.")

    with connect() as conn:
        if parent_id is not None:
            parent = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (parent_id, project_id),
            ).fetchone()
            if not parent:
                raise ValueError("Родительская папка не найдена.")

        duplicate = conn.execute(
            """
            SELECT id FROM document_folders
            WHERE project_id = ? AND name = ? AND deleted_at IS NULL
              AND ((parent_id IS NULL AND ? IS NULL) OR parent_id = ?)
            """,
            (project_id, clean, parent_id, parent_id),
        ).fetchone()
        if duplicate:
            raise ValueError("Папка с таким названием уже существует.")

        cur = conn.execute(
            """
            INSERT INTO document_folders(project_id, parent_id, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, parent_id, clean, utc_now()),
        )
        row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at, deleted_at, trash_path
            FROM document_folders WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


def list_document_folders(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                f.id, f.project_id, f.parent_id, f.name, f.created_at,
                COUNT(d.id) AS document_count
            FROM document_folders f
            LEFT JOIN documents d ON d.folder_id = f.id AND d.deleted_at IS NULL
            WHERE f.project_id = ? AND f.deleted_at IS NULL
            GROUP BY f.id
            ORDER BY f.parent_id IS NOT NULL, f.name COLLATE NOCASE
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_document_folder_parts(
    project_id: int,
    folder_id: int | None,
    *,
    include_deleted: bool = False,
) -> list[str]:
    if folder_id is None:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, parent_id, name, deleted_at
            FROM document_folders WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()

    by_id = {int(row["id"]): dict(row) for row in rows}
    current = by_id.get(int(folder_id))
    if not current:
        raise ValueError("Папка не найдена.")

    parts: list[str] = []
    seen: set[int] = set()
    while current:
        current_id = int(current["id"])
        if current_id in seen:
            raise ValueError("Обнаружен цикл в структуре папок.")
        seen.add(current_id)
        if current.get("deleted_at") and not include_deleted:
            raise ValueError("Папка находится в корзине.")
        parts.insert(0, str(current["name"]))
        parent_id = current.get("parent_id")
        current = by_id.get(int(parent_id)) if parent_id is not None else None
    return parts


def get_document(project_id: int, document_id: int, *, include_deleted: bool = False) -> dict | None:
    where_deleted = "" if include_deleted else " AND d.deleted_at IS NULL"
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT d.id, d.project_id, d.folder_id, d.filename, d.stored_path,
                   d.mime_type, d.sha256, d.size_bytes, d.created_at,
                   d.deleted_at, d.trash_path, f.name AS folder_name,
                   COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_folders f ON f.id = d.folder_id
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE d.id = ? AND d.project_id = ?{where_deleted}
            GROUP BY d.id
            """,
            (document_id, project_id),
        ).fetchone()
    return dict(row) if row else None


def find_document_by_sha(project_id: int, sha256: str, *, include_deleted: bool = True) -> dict | None:
    where_deleted = "" if include_deleted else " AND deleted_at IS NULL"
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at, deleted_at, trash_path
            FROM documents
            WHERE project_id = ? AND sha256 = ?{where_deleted}
            LIMIT 1
            """,
            (project_id, sha256),
        ).fetchone()
    return dict(row) if row else None


def add_document(
    project_id: int,
    filename: str,
    stored_path: str,
    mime_type: str | None,
    sha256: str,
    size_bytes: int,
    chunks: list[str],
    folder_id: int | None = None,
) -> dict:
    with connect() as conn:
        if folder_id is not None:
            folder = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (folder_id, project_id),
            ).fetchone()
            if not folder:
                raise ValueError("Папка не найдена.")

        existing = conn.execute(
            """
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at, deleted_at, trash_path
            FROM documents WHERE project_id = ? AND sha256 = ?
            """,
            (project_id, sha256),
        ).fetchone()
        if existing:
            existing_dict = dict(existing)
            if existing_dict.get("deleted_at"):
                conn.execute(
                    """
                    UPDATE documents
                    SET folder_id = ?, filename = ?, stored_path = ?, mime_type = ?,
                        size_bytes = ?, deleted_at = NULL, trash_path = NULL
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        folder_id, filename, stored_path, mime_type, size_bytes,
                        existing_dict["id"], project_id,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                           sha256, size_bytes, created_at, deleted_at, trash_path
                    FROM documents WHERE id = ?
                    """,
                    (existing_dict["id"],),
                ).fetchone()
                return dict(row)
            return existing_dict

        cur = conn.execute(
            """
            INSERT INTO documents(
                project_id, folder_id, filename, stored_path, mime_type, sha256, size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, folder_id, filename, stored_path, mime_type,
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
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at, deleted_at, trash_path
            FROM documents WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row)


def replace_document_chunks(
    project_id: int,
    document_id: int,
    chunks: list[str],
) -> int:
    """Atomically replace searchable chunks after a verified re-extraction/OCR pass."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM documents
            WHERE id=? AND project_id=? AND deleted_at IS NULL
            """,
            (document_id, project_id),
        ).fetchone()
        if not row:
            raise ValueError("Документ не найден в текущем проекте.")
        conn.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        now = utc_now()
        for index, content in enumerate(chunks):
            clean = str(content or "").strip()
            if not clean:
                continue
            conn.execute(
                """
                INSERT INTO document_chunks(document_id,chunk_index,content,created_at)
                VALUES(?,?,?,?)
                """,
                (document_id, index, clean, now),
            )
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM document_chunks WHERE document_id=?",
            (document_id,),
        ).fetchone()["n"]
    return int(count)


def update_document_storage_path(project_id: int, document_id: int, stored_path: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE documents SET stored_path = ?
            WHERE id = ? AND project_id = ?
            """,
            (stored_path, document_id, project_id),
        )


def list_documents(project_id: int, folder_id: int | None = None) -> list[dict]:
    where = "WHERE d.project_id = ? AND d.deleted_at IS NULL"
    params: list[object] = [project_id]
    if folder_id is not None:
        where += " AND d.folder_id = ?"
        params.append(folder_id)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                d.id, d.folder_id, d.filename, d.stored_path, d.mime_type,
                d.sha256, d.size_bytes, d.created_at, f.name AS folder_name,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_folders f ON f.id = d.folder_id
            LEFT JOIN document_chunks c ON c.document_id = d.id
            {where}
            GROUP BY d.id
            ORDER BY d.id DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_deleted_documents(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.folder_id, d.filename, d.mime_type, d.sha256,
                   d.size_bytes, d.created_at, d.deleted_at, d.trash_path,
                   COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE d.project_id = ? AND d.deleted_at IS NOT NULL
              AND d.trash_path IS NOT NULL
            GROUP BY d.id
            ORDER BY d.deleted_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_deleted_document_folders(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at, deleted_at, trash_path
            FROM document_folders
            WHERE project_id = ? AND deleted_at IS NOT NULL AND trash_path IS NOT NULL
            ORDER BY deleted_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_document_deleted(project_id: int, document_id: int, trash_path: str) -> dict | None:
    deleted_at = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE documents
            SET deleted_at = ?, trash_path = ?
            WHERE id = ? AND project_id = ? AND deleted_at IS NULL
            """,
            (deleted_at, trash_path, document_id, project_id),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute(
            """
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at, deleted_at, trash_path
            FROM documents WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row)


def restore_document_record(
    project_id: int,
    document_id: int,
    stored_path: str,
    folder_id: int | None,
) -> dict | None:
    with connect() as conn:
        if folder_id is not None:
            folder = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (folder_id, project_id),
            ).fetchone()
            if not folder:
                folder_id = None

        cur = conn.execute(
            """
            UPDATE documents
            SET stored_path = ?, folder_id = ?, deleted_at = NULL, trash_path = NULL
            WHERE id = ? AND project_id = ? AND deleted_at IS NOT NULL
            """,
            (stored_path, folder_id, document_id, project_id),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute(
            """
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at, deleted_at, trash_path
            FROM documents WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row)


def _folder_descendants(rows: list[dict], root_id: int) -> list[int]:
    children: dict[int | None, list[int]] = {}
    for row in rows:
        parent = row.get("parent_id")
        children.setdefault(int(parent) if parent is not None else None, []).append(int(row["id"]))

    result: list[int] = []
    stack = [int(root_id)]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        stack.extend(children.get(item, []))
    return result


def mark_document_folder_deleted(project_id: int, folder_id: int, trash_path: str) -> dict | None:
    deleted_at = utc_now()
    with connect() as conn:
        root = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at
            FROM document_folders
            WHERE id = ? AND project_id = ? AND deleted_at IS NULL
            """,
            (folder_id, project_id),
        ).fetchone()
        if not root:
            return None

        folder_rows = [
            dict(row) for row in conn.execute(
                """
                SELECT id, parent_id FROM document_folders
                WHERE project_id = ? AND deleted_at IS NULL
                """,
                (project_id,),
            ).fetchall()
        ]
        folder_ids = _folder_descendants(folder_rows, folder_id)
        placeholders = ",".join("?" for _ in folder_ids)

        document_rows = conn.execute(
            f"""
            SELECT id FROM documents
            WHERE project_id = ? AND deleted_at IS NULL
              AND folder_id IN ({placeholders})
            """,
            [project_id, *folder_ids],
        ).fetchall()
        document_ids = [int(row["id"]) for row in document_rows]

        conn.execute(
            f"""
            UPDATE document_folders SET deleted_at = ?
            WHERE project_id = ? AND id IN ({placeholders}) AND deleted_at IS NULL
            """,
            [deleted_at, project_id, *folder_ids],
        )
        conn.execute(
            """
            UPDATE document_folders SET trash_path = ?
            WHERE id = ? AND project_id = ?
            """,
            (trash_path, folder_id, project_id),
        )
        if document_ids:
            doc_marks = ",".join("?" for _ in document_ids)
            conn.execute(
                f"""
                UPDATE documents SET deleted_at = ?, trash_path = NULL
                WHERE project_id = ? AND id IN ({doc_marks})
                """,
                [deleted_at, project_id, *document_ids],
            )

    result = dict(root)
    result.update({
        "deleted_at": deleted_at,
        "trash_path": trash_path,
        "folder_ids": folder_ids,
        "document_ids": document_ids,
    })
    return result


def restore_document_folder_record(
    project_id: int,
    folder_id: int,
    *,
    restored_name: str | None = None,
) -> dict | None:
    with connect() as conn:
        root_row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at, deleted_at, trash_path
            FROM document_folders
            WHERE id = ? AND project_id = ? AND deleted_at IS NOT NULL
            """,
            (folder_id, project_id),
        ).fetchone()
        if not root_row:
            return None
        root = dict(root_row)
        deleted_at = root["deleted_at"]

        all_rows = [
            dict(row) for row in conn.execute(
                """
                SELECT id, parent_id, deleted_at FROM document_folders
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchall()
        ]
        tree_ids = _folder_descendants(all_rows, folder_id)
        restore_ids = [
            item_id for item_id in tree_ids
            if next((r for r in all_rows if int(r["id"]) == item_id), {}).get("deleted_at") == deleted_at
        ]
        placeholders = ",".join("?" for _ in restore_ids)

        parent_id = root.get("parent_id")
        if parent_id is not None:
            parent = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (parent_id, project_id),
            ).fetchone()
            if not parent:
                parent_id = None

        name = restored_name or root["name"]
        duplicate = conn.execute(
            """
            SELECT id FROM document_folders
            WHERE project_id = ? AND deleted_at IS NULL AND name = ?
              AND ((parent_id IS NULL AND ? IS NULL) OR parent_id = ?)
            LIMIT 1
            """,
            (project_id, name, parent_id, parent_id),
        ).fetchone()
        if duplicate:
            name = f"{name} (восстановлено {folder_id})"

        conn.execute(
            f"""
            UPDATE document_folders SET deleted_at = NULL
            WHERE project_id = ? AND id IN ({placeholders}) AND deleted_at = ?
            """,
            [project_id, *restore_ids, deleted_at],
        )
        conn.execute(
            """
            UPDATE document_folders
            SET name = ?, parent_id = ?, trash_path = NULL
            WHERE id = ? AND project_id = ?
            """,
            (name, parent_id, folder_id, project_id),
        )
        if restore_ids:
            conn.execute(
                f"""
                UPDATE documents SET deleted_at = NULL
                WHERE project_id = ? AND folder_id IN ({placeholders})
                  AND deleted_at = ? AND trash_path IS NULL
                """,
                [project_id, *restore_ids, deleted_at],
            )

        row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, created_at, deleted_at, trash_path
            FROM document_folders WHERE id = ?
            """,
            (folder_id,),
        ).fetchone()
    return dict(row)


def get_document_chunks(
    project_id: int,
    document_id: int,
    *,
    start: int = 0,
    limit: int = 12,
) -> list[dict]:
    start = max(0, int(start))
    limit = max(1, min(int(limit), 40))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.chunk_index, c.content,
                   d.id AS document_id, d.filename
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.id = ? AND d.project_id = ? AND d.deleted_at IS NULL
              AND c.chunk_index >= ?
            ORDER BY c.chunk_index ASC
            LIMIT ?
            """,
            (document_id, project_id, start, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def move_document_record(
    project_id: int,
    document_id: int,
    folder_id: int | None,
    stored_path: str,
) -> dict | None:
    with connect() as conn:
        if folder_id is not None:
            folder = conn.execute(
                """
                SELECT id FROM document_folders
                WHERE id = ? AND project_id = ? AND deleted_at IS NULL
                """,
                (folder_id, project_id),
            ).fetchone()
            if not folder:
                raise ValueError("Целевая папка не найдена.")
        cur = conn.execute(
            """
            UPDATE documents SET folder_id = ?, stored_path = ?
            WHERE id = ? AND project_id = ? AND deleted_at IS NULL
            """,
            (folder_id, stored_path, document_id, project_id),
        )
        if cur.rowcount != 1:
            return None
        row = conn.execute(
            """
            SELECT id, project_id, folder_id, filename, stored_path, mime_type,
                   sha256, size_bytes, created_at
            FROM documents WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row)


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
            WHERE d.project_id = ? AND d.deleted_at IS NULL
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
            "SELECT COUNT(*) AS n FROM documents WHERE project_id = ? AND deleted_at IS NULL",
            (project_id,),
        ).fetchone()["n"]
        document_chunks = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.project_id = ? AND d.deleted_at IS NULL
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
        waiting_workflows = conn.execute(
            """
            SELECT COUNT(*) AS n FROM agent_workflows
            WHERE project_id = ? AND status = 'waiting_permission'
            """,
            (project_id,),
        ).fetchone()["n"]
        recovering_workflows = conn.execute(
            """
            SELECT COUNT(*) AS n FROM agent_workflows
            WHERE project_id = ? AND status = 'recovering'
            """,
            (project_id,),
        ).fetchone()["n"]
        recovery_operations = conn.execute(
            """
            SELECT COUNT(*) AS n FROM tool_operations
            WHERE project_id = ? AND status = 'recovery_required'
            """,
            (project_id,),
        ).fetchone()["n"]
        pending_permissions = conn.execute(
            """
            SELECT COUNT(*) AS n FROM permission_requests
            WHERE project_id = ? AND status = 'pending'
            """,
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
        "waiting_workflows": int(waiting_workflows),
        "recovering_workflows": int(recovering_workflows),
        "recovery_operations": int(recovery_operations),
        "pending_permissions": int(pending_permissions),
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




WORKFLOW_STATUSES = {
    "running", "waiting_permission", "recovering",
    "completed", "failed", "cancelled",
}

WORKFLOW_STEP_STATUSES = {
    "planned", "running", "waiting_permission", "recovery_required",
    "completed", "failed", "skipped", "cancelled",
}

TOOL_OPERATION_STATUSES = {
    "planned", "running", "verifying", "recovery_required",
    "executed", "failed", "cancelled",
}


def _loads_json(value: str | None, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def create_agent_workflow(
    project_id: int,
    conversation_id: int | None,
    agent_run_id: int | None,
    request_key: str,
    goal: str,
    route: dict,
    conversation_context: list[dict],
    max_steps: int,
) -> dict:
    clean_key = request_key.strip()
    if not clean_key:
        raise ValueError("request_key workflow не может быть пустым.")
    now = utc_now()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM agent_workflows
            WHERE project_id = ? AND request_key = ?
            LIMIT 1
            """,
            (project_id, clean_key),
        ).fetchone()
        if existing:
            row = existing
        else:
            cur = conn.execute(
                """
                INSERT INTO agent_workflows(
                    project_id, conversation_id, agent_run_id, request_key, goal,
                    status, route_json, conversation_context_json,
                    planner_mode, current_step, max_steps,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, 'model', 0, ?, ?, ?)
                """,
                (
                    project_id,
                    conversation_id,
                    agent_run_id,
                    clean_key,
                    goal,
                    json.dumps(route, ensure_ascii=False),
                    json.dumps(conversation_context, ensure_ascii=False),
                    max_steps,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM agent_workflows WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
    return _workflow_row(row)


def _workflow_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["route"] = _loads_json(item.pop("route_json", None), {})
    item["conversation_context"] = _loads_json(
        item.pop("conversation_context_json", None),
        [],
    )
    item["result"] = _loads_json(item.pop("result_json", None), None)
    item["error"] = _loads_json(item.pop("error_json", None), None)
    return item


def get_agent_workflow(
    workflow_id: int,
    project_id: int | None = None,
) -> dict | None:
    with connect() as conn:
        if project_id is None:
            row = conn.execute(
                "SELECT * FROM agent_workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM agent_workflows WHERE id = ? AND project_id = ?",
                (workflow_id, project_id),
            ).fetchone()
    return _workflow_row(row)


def get_agent_workflow_by_request_key(
    project_id: int,
    request_key: str,
) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM agent_workflows
            WHERE project_id = ? AND request_key = ?
            LIMIT 1
            """,
            (project_id, request_key),
        ).fetchone()
    return _workflow_row(row)


def list_agent_workflows(
    project_id: int,
    *,
    statuses: tuple[str, ...] | None = None,
    limit: int = 50,
) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    params: list[object] = [project_id]
    where = "WHERE project_id = ?"
    if statuses:
        invalid = set(statuses) - WORKFLOW_STATUSES
        if invalid:
            raise ValueError("Недопустимый статус workflow.")
        placeholders = ",".join("?" for _ in statuses)
        where += f" AND status IN ({placeholders})"
        params.extend(statuses)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM agent_workflows
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_workflow_row(row) for row in rows]


def update_agent_workflow(
    workflow_id: int,
    *,
    status: str | None = None,
    planner_mode: str | None = None,
    current_step: int | None = None,
    pending_permission_id: int | None | object = ...,
    result: dict | None | object = ...,
    error: dict | None | object = ...,
    finished: bool = False,
) -> dict | None:
    assignments = ["updated_at = ?"]
    params: list[object] = [utc_now()]
    if status is not None:
        if status not in WORKFLOW_STATUSES:
            raise ValueError("Недопустимый статус workflow.")
        assignments.append("status = ?")
        params.append(status)
    if planner_mode is not None:
        assignments.append("planner_mode = ?")
        params.append(planner_mode)
    if current_step is not None:
        assignments.append("current_step = ?")
        params.append(int(current_step))
    if pending_permission_id is not ...:
        assignments.append("pending_permission_id = ?")
        params.append(pending_permission_id)
    if result is not ...:
        assignments.append("result_json = ?")
        params.append(
            json.dumps(result, ensure_ascii=False) if result is not None else None
        )
    if error is not ...:
        assignments.append("error_json = ?")
        params.append(
            json.dumps(error, ensure_ascii=False) if error is not None else None
        )
    if finished:
        assignments.append("finished_at = ?")
        params.append(utc_now())
    params.append(workflow_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE agent_workflows SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
    return get_agent_workflow(workflow_id)


def create_workflow_step(
    workflow_id: int,
    step_index: int,
    kind: str,
    reason: str,
    *,
    tool_name: str | None = None,
    arguments: dict | None = None,
    status: str = "planned",
    idempotency_key: str,
) -> dict:
    if kind not in {"tool", "finish"}:
        raise ValueError("Недопустимый тип workflow step.")
    if status not in WORKFLOW_STEP_STATUSES:
        raise ValueError("Недопустимый статус workflow step.")
    now = utc_now()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM workflow_steps
            WHERE workflow_id = ? AND step_index = ?
            LIMIT 1
            """,
            (workflow_id, step_index),
        ).fetchone()
        if existing:
            return _workflow_step_row(existing)
        cur = conn.execute(
            """
            INSERT INTO workflow_steps(
                workflow_id, step_index, kind, tool_name, reason,
                arguments_json, status, idempotency_key,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                step_index,
                kind,
                tool_name,
                reason,
                json.dumps(arguments or {}, ensure_ascii=False),
                status,
                idempotency_key,
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM workflow_steps WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _workflow_step_row(row)


def _workflow_step_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["arguments"] = _loads_json(item.pop("arguments_json", None), {})
    item["result"] = _loads_json(item.pop("result_json", None), None)
    return item


def get_workflow_step(step_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_steps WHERE id = ?",
            (step_id,),
        ).fetchone()
    return _workflow_step_row(row)


def list_workflow_steps(workflow_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM workflow_steps
            WHERE workflow_id = ?
            ORDER BY step_index ASC, id ASC
            """,
            (workflow_id,),
        ).fetchall()
    return [_workflow_step_row(row) for row in rows]


def update_workflow_step(
    step_id: int,
    *,
    status: str | None = None,
    result: dict | None | object = ...,
    permission_request_id: int | None | object = ...,
    increment_retry: bool = False,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> dict | None:
    assignments = ["updated_at = ?"]
    params: list[object] = [utc_now()]
    if status is not None:
        if status not in WORKFLOW_STEP_STATUSES:
            raise ValueError("Недопустимый статус workflow step.")
        assignments.append("status = ?")
        params.append(status)
    if result is not ...:
        assignments.append("result_json = ?")
        params.append(
            json.dumps(result, ensure_ascii=False) if result is not None else None
        )
    if permission_request_id is not ...:
        assignments.append("permission_request_id = ?")
        params.append(permission_request_id)
    if increment_retry:
        assignments.append("retry_count = retry_count + 1")
    if mark_started:
        assignments.append("started_at = COALESCE(started_at, ?)")
        params.append(utc_now())
    if mark_finished:
        assignments.append("finished_at = ?")
        params.append(utc_now())
    params.append(step_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE workflow_steps SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
    return get_workflow_step(step_id)


def record_workflow_event(
    workflow_id: int,
    event_type: str,
    payload: dict | None = None,
) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO workflow_events(workflow_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                workflow_id,
                event_type,
                json.dumps(payload or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM workflow_events WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    item = dict(row)
    item["payload"] = _loads_json(item.pop("payload_json", None), {})
    return item


def list_workflow_events(workflow_id: int, limit: int = 200) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM workflow_events
            WHERE workflow_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (workflow_id, max(1, min(int(limit), 500))),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["payload"] = _loads_json(item.pop("payload_json", None), {})
        result.append(item)
    return result


def create_tool_operation(
    project_id: int,
    tool_name: str,
    idempotency_key: str,
    arguments: dict,
    *,
    workflow_id: int | None = None,
    workflow_step_id: int | None = None,
    permission_request_id: int | None = None,
    preflight: dict | None = None,
) -> dict:
    now = utc_now()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM tool_operations
            WHERE project_id = ? AND idempotency_key = ?
            LIMIT 1
            """,
            (project_id, idempotency_key),
        ).fetchone()
        if existing:
            return _tool_operation_row(existing)
        cur = conn.execute(
            """
            INSERT INTO tool_operations(
                project_id, workflow_id, workflow_step_id, permission_request_id,
                tool_name, idempotency_key, arguments_json, preflight_json,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
            """,
            (
                project_id,
                workflow_id,
                workflow_step_id,
                permission_request_id,
                tool_name,
                idempotency_key,
                json.dumps(arguments, ensure_ascii=False),
                json.dumps(preflight or {}, ensure_ascii=False),
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM tool_operations WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return _tool_operation_row(row)


def _tool_operation_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["arguments"] = _loads_json(item.pop("arguments_json", None), {})
    item["preflight"] = _loads_json(item.pop("preflight_json", None), {})
    item["result"] = _loads_json(item.pop("result_json", None), None)
    item["error"] = _loads_json(item.pop("error_json", None), None)
    return item


def get_tool_operation(operation_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM tool_operations WHERE id = ?",
            (operation_id,),
        ).fetchone()
    return _tool_operation_row(row)


def get_tool_operation_by_key(project_id: int, idempotency_key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM tool_operations
            WHERE project_id = ? AND idempotency_key = ?
            LIMIT 1
            """,
            (project_id, idempotency_key),
        ).fetchone()
    return _tool_operation_row(row)


def link_tool_operation_permission(
    operation_id: int,
    permission_request_id: int,
) -> dict | None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE tool_operations
            SET permission_request_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (permission_request_id, utc_now(), operation_id),
        )
    return get_tool_operation(operation_id)


def update_tool_operation(
    operation_id: int,
    *,
    status: str | None = None,
    result: dict | None | object = ...,
    error: dict | None | object = ...,
    increment_attempt: bool = False,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> dict | None:
    assignments = ["updated_at = ?"]
    params: list[object] = [utc_now()]
    if status is not None:
        if status not in TOOL_OPERATION_STATUSES:
            raise ValueError("Недопустимый статус tool operation.")
        assignments.append("status = ?")
        params.append(status)
    if result is not ...:
        assignments.append("result_json = ?")
        params.append(
            json.dumps(result, ensure_ascii=False) if result is not None else None
        )
    if error is not ...:
        assignments.append("error_json = ?")
        params.append(
            json.dumps(error, ensure_ascii=False) if error is not None else None
        )
    if increment_attempt:
        assignments.append("attempt_count = attempt_count + 1")
    if mark_started:
        assignments.append("started_at = COALESCE(started_at, ?)")
        params.append(utc_now())
    if mark_finished:
        assignments.append("finished_at = ?")
        params.append(utc_now())
    params.append(operation_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE tool_operations SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
    return get_tool_operation(operation_id)


def list_recoverable_tool_operations(project_id: int | None = None) -> list[dict]:
    params: list[object] = []
    where = "WHERE status IN ('running','verifying','recovery_required')"
    if project_id is not None:
        where += " AND project_id = ?"
        params.append(project_id)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM tool_operations
            {where}
            ORDER BY id ASC
            """,
            params,
        ).fetchall()
    return [_tool_operation_row(row) for row in rows]


def mark_interrupted_runtime_for_recovery() -> dict:
    now = utc_now()
    with connect() as conn:
        workflows_running = conn.execute(
            """
            UPDATE agent_workflows
            SET status = 'recovering', updated_at = ?
            WHERE status = 'running'
            """,
            (now,),
        ).rowcount
        workflows_permission = conn.execute(
            """
            UPDATE agent_workflows
            SET status = 'recovering', updated_at = ?
            WHERE status = 'waiting_permission'
              AND pending_permission_id IN (
                  SELECT id FROM permission_requests
                  WHERE status IN ('approved','executed','failed','denied')
              )
            """,
            (now,),
        ).rowcount
        workflows = int(workflows_running) + int(workflows_permission)
        steps = conn.execute(
            """
            UPDATE workflow_steps
            SET status = 'recovery_required', updated_at = ?
            WHERE status = 'running'
            """,
            (now,),
        ).rowcount
        operations = conn.execute(
            """
            UPDATE tool_operations
            SET status = 'recovery_required', updated_at = ?
            WHERE status IN ('running','verifying')
            """,
            (now,),
        ).rowcount
        cancelled_tasks = conn.execute(
            """
            UPDATE tasks
            SET status = 'cancelled', finished_at = ?
            WHERE status = 'running' AND cancel_requested = 1
            """,
            (now,),
        ).rowcount
        requeued_tasks = conn.execute(
            """
            UPDATE tasks
            SET status = 'queued', started_at = NULL
            WHERE status = 'running' AND cancel_requested = 0
            """
        ).rowcount
    return {
        "workflows": int(workflows),
        "steps": int(steps),
        "operations": int(operations),
        "tasks_requeued": int(requeued_tasks),
        "tasks_cancelled": int(cancelled_tasks),
    }


def record_audit_event(
    project_id: int,
    actor: str,
    event_type: str,
    summary: str,
    *,
    conversation_id: int | None = None,
    workflow_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    details: dict | None = None,
) -> dict:
    if actor not in {"user", "miyori", "system"}:
        raise ValueError("Недопустимый actor audit event.")
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_events(
                project_id, conversation_id, workflow_id, actor, event_type,
                entity_type, entity_id, summary, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                conversation_id,
                workflow_id,
                actor,
                event_type,
                entity_type,
                None if entity_id is None else str(entity_id),
                summary,
                json.dumps(details or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM audit_events WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    item = dict(row)
    item["details"] = _loads_json(item.pop("details_json", None), {})
    return item


def list_audit_events(
    project_id: int,
    *,
    workflow_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    where = "WHERE project_id = ?"
    params: list[object] = [project_id]
    if workflow_id is not None:
        where += " AND workflow_id = ?"
        params.append(workflow_id)
    params.append(max(1, min(int(limit), 500)))
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM audit_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["details"] = _loads_json(item.pop("details_json", None), {})
        result.append(item)
    return result



def start_agent_run(project_id: int, conversation_id: int | None, goal: str, max_steps: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_runs(project_id, conversation_id, goal, status, max_steps, started_at)
            VALUES (?, ?, ?, 'running', ?, ?)
            """,
            (project_id, conversation_id, goal, max_steps, utc_now()),
        )
        return int(cur.lastrowid)


def record_agent_action(
    run_id: int,
    step_index: int,
    reason: str,
    status: str,
    tool_name: str | None = None,
    arguments: dict | None = None,
    result: dict | None = None,
) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_actions(
                run_id, step_index, tool_name, reason,
                arguments_json, result_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                step_index,
                tool_name,
                reason,
                json.dumps(arguments or {}, ensure_ascii=False),
                json.dumps(result or {}, ensure_ascii=False),
                status,
                utc_now(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, run_id, step_index, tool_name, reason, arguments_json,
                   result_json, status, created_at
            FROM agent_actions WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    item = dict(row)
    item["arguments"] = json.loads(item.pop("arguments_json") or "{}")
    item["result"] = json.loads(item.pop("result_json") or "{}")
    return item


def set_agent_run_status(
    run_id: int,
    status: str,
    *,
    finished: bool = False,
) -> None:
    with connect() as conn:
        if finished:
            conn.execute(
                """
                UPDATE agent_runs SET status = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, utc_now(), run_id),
            )
        else:
            conn.execute(
                """
                UPDATE agent_runs SET status = ?, finished_at = NULL
                WHERE id = ?
                """,
                (status, run_id),
            )


def finish_agent_run(run_id: int, status: str = "completed") -> None:
    set_agent_run_status(run_id, status, finished=True)


def get_agent_trace(run_id: int) -> dict | None:
    with connect() as conn:
        run = conn.execute(
            """
            SELECT id, project_id, conversation_id, goal, status, max_steps,
                   started_at, finished_at
            FROM agent_runs WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if not run:
            return None
        rows = conn.execute(
            """
            SELECT id, step_index, tool_name, reason, arguments_json,
                   result_json, status, created_at
            FROM agent_actions
            WHERE run_id = ?
            ORDER BY step_index ASC, id ASC
            """,
            (run_id,),
        ).fetchall()

    actions = []
    for row in rows:
        item = dict(row)
        item["arguments"] = json.loads(item.pop("arguments_json") or "{}")
        item["result"] = json.loads(item.pop("result_json") or "{}")
        actions.append(item)

    result = dict(run)
    result["actions"] = actions
    return result



def create_permission_request(
    project_id: int,
    tool_name: str,
    arguments: dict,
    reason: str | None = None,
    *,
    workflow_id: int | None = None,
    workflow_step_id: int | None = None,
    tool_operation_id: int | None = None,
    idempotency_key: str | None = None,
    preview: dict | None = None,
) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO permission_requests(
                project_id, tool_name, arguments_json, status, reason,
                workflow_id, workflow_step_id, tool_operation_id, idempotency_key, preview_json,
                created_at
            ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                tool_name,
                json.dumps(arguments, ensure_ascii=False),
                reason,
                workflow_id,
                workflow_step_id,
                tool_operation_id,
                idempotency_key,
                json.dumps(preview or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        row = conn.execute(
            """
            SELECT id, project_id, tool_name, arguments_json, status, reason,
                   workflow_id, workflow_step_id, tool_operation_id, idempotency_key, preview_json,
                   created_at, decided_at, executed_at
            FROM permission_requests WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    item = dict(row)
    item["arguments"] = json.loads(item.pop("arguments_json"))
    item["preview"] = _loads_json(item.pop("preview_json", None), {})
    return item


def list_permission_requests(project_id: int, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, tool_name, arguments_json, status, reason,
                   result_json, workflow_id, workflow_step_id, tool_operation_id, idempotency_key,
                   preview_json, created_at, decided_at, executed_at
            FROM permission_requests
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["arguments"] = json.loads(item.pop("arguments_json"))
        item["preview"] = _loads_json(item.pop("preview_json", None), {})
        raw_result = item.pop("result_json")
        item["result"] = json.loads(raw_result) if raw_result else None
        result.append(item)
    return result


def get_permission_request(project_id: int, request_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, tool_name, arguments_json, status, reason,
                   result_json, workflow_id, workflow_step_id, tool_operation_id, idempotency_key,
                   preview_json, created_at, decided_at, executed_at
            FROM permission_requests
            WHERE id = ? AND project_id = ?
            """,
            (request_id, project_id),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["arguments"] = json.loads(item.pop("arguments_json"))
    item["preview"] = _loads_json(item.pop("preview_json", None), {})
    raw_result = item.pop("result_json")
    item["result"] = json.loads(raw_result) if raw_result else None
    return item


def decide_permission_request(project_id: int, request_id: int, approved: bool) -> dict | None:
    status = "approved" if approved else "denied"
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE permission_requests
            SET status = ?, decided_at = ?
            WHERE id = ? AND project_id = ? AND status = 'pending'
            """,
            (status, utc_now(), request_id, project_id),
        )
        if cur.rowcount != 1:
            return None
    return get_permission_request(project_id, request_id)


def finish_permission_execution(
    project_id: int,
    request_id: int,
    status: str,
    result: dict,
) -> dict | None:
    if status not in {"executed", "failed"}:
        raise ValueError("Недопустимый статус выполнения разрешения.")
    with connect() as conn:
        conn.execute(
            """
            UPDATE permission_requests
            SET status = ?, result_json = ?, executed_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                status,
                json.dumps(result, ensure_ascii=False),
                utc_now(),
                request_id,
                project_id,
            ),
        )
    return get_permission_request(project_id, request_id)


def record_hand_event(
    project_id: int,
    tool_name: str,
    action: str,
    arguments: dict,
    result: dict,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO hand_events(
                project_id, tool_name, action, arguments_json, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                tool_name,
                action,
                json.dumps(arguments, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                utc_now(),
            ),
        )
