"""Only actual Cloud.ru usage and measured request duration, never invented tokens."""
from __future__ import annotations
import sqlite3
from .db import connect


def init_chat_metrics_db() -> None:
    with connect() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS chat_model_usage (
            assistant_message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms INTEGER NOT NULL,
            estimated_cost_rub REAL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_chat_usage_project ON chat_model_usage(project_id,created_at)")


def store_model_usage(project_id: int, message_id: int, measured: dict) -> None:
    with connect() as db:
        db.execute("""
        INSERT OR IGNORE INTO chat_model_usage(
            assistant_message_id,project_id,model,prompt_tokens,completion_tokens,
            total_tokens,latency_ms,estimated_cost_rub
        ) VALUES(?,?,?,?,?,?,?,?)
        """,(
            message_id,project_id,str(measured.get("model") or "unknown"),
            measured.get("prompt_tokens"),measured.get("completion_tokens"),
            measured.get("total_tokens"),int(measured.get("latency_ms") or 0),
            measured.get("estimated_cost_rub")
        ))


def model_usage_summary(project_id: int, days: int = 30) -> dict:
    days=max(1,min(365,int(days)))
    with connect() as db:
        row=db.execute("""
            SELECT COUNT(*) requests, COUNT(total_tokens) measured_requests,
                   SUM(COALESCE(prompt_tokens,0)) prompt_tokens,
                   SUM(COALESCE(completion_tokens,0)) completion_tokens,
                   SUM(COALESCE(total_tokens,0)) total_tokens,
                   SUM(latency_ms) total_latency_ms,
                   SUM(estimated_cost_rub) estimated_cost_rub,
                   COUNT(estimated_cost_rub) rated_requests
            FROM chat_model_usage
            WHERE project_id=? AND created_at >= datetime('now', ?)
        """,(project_id,f"-{days} days")).fetchone()
    data=dict(row)
    return {
        "days":days,
        "requests":data["requests"],
        "measured_requests":data["measured_requests"],
        "prompt_tokens":data["prompt_tokens"] or 0,
        "completion_tokens":data["completion_tokens"] or 0,
        "total_tokens":data["total_tokens"] or 0,
        "total_latency_ms":data["total_latency_ms"] or 0,
        # A partial priced subset must never be shown as a complete total.
        "estimated_cost_rub":(
            data["estimated_cost_rub"] if data["rated_requests"] == data["requests"]
            and data["requests"] else None
        ),
        "billing_verified":False,
        "note":"Локальный расчёт по фактическому usage API. Не является счётом Cloud.ru.",
    }
