from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from .db import connect

NEXUS_EVENT_SCHEMA_VERSION = "1.0.0"

_SOURCE_RANK = {
    "audit": 1,
    "workflow": 2,
    "task": 3,
}


@dataclass(frozen=True)
class EventCursor:
    created_at: str
    source_rank: int
    source_id: int


def _encode_cursor(cursor: EventCursor) -> str:
    raw = json.dumps(
        {
            "t": cursor.created_at,
            "r": cursor.source_rank,
            "i": cursor.source_id,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> EventCursor | None:
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")
        )
        created_at = str(payload["t"])
        source_rank = int(payload["r"])
        source_id = int(payload["i"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Некорректный NEXUS event cursor.") from exc
    if source_rank not in _SOURCE_RANK.values() or source_id <= 0 or not created_at:
        raise ValueError("Некорректный NEXUS event cursor.")
    return EventCursor(created_at, source_rank, source_id)


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _severity(event_type: str) -> str:
    value = str(event_type or "").casefold()
    if any(token in value for token in ("failed", "error", "rejected")):
        return "error"
    if any(
        token in value
        for token in ("waiting", "permission", "recovery", "cancel", "denied")
    ):
        return "warning"
    if any(token in value for token in ("completed", "executed", "verified", "ready")):
        return "success"
    return "info"


def _task_payload(details: str | None) -> dict:
    parsed = _loads(details, None)
    if isinstance(parsed, dict):
        return parsed
    return {"details": str(details or "")} if details else {}


_EVENT_STREAM_SQL = """
    SELECT *
    FROM (
        SELECT
            'audit' AS source,
            1 AS source_rank,
            ae.id AS source_id,
            ae.event_type AS event_type,
            ae.created_at AS created_at,
            ae.summary AS summary,
            ae.details_json AS payload_json,
            ae.actor AS actor,
            ae.entity_type AS entity_type,
            ae.entity_id AS entity_id,
            ae.workflow_id AS workflow_id,
            NULL AS task_id
        FROM audit_events ae
        WHERE ae.project_id = ?

        UNION ALL

        SELECT
            'workflow' AS source,
            2 AS source_rank,
            we.id AS source_id,
            we.event_type AS event_type,
            we.created_at AS created_at,
            NULL AS summary,
            we.payload_json AS payload_json,
            'miyori' AS actor,
            'workflow' AS entity_type,
            CAST(we.workflow_id AS TEXT) AS entity_id,
            we.workflow_id AS workflow_id,
            NULL AS task_id
        FROM workflow_events we
        JOIN agent_workflows aw ON aw.id = we.workflow_id
        WHERE aw.project_id = ?

        UNION ALL

        SELECT
            'task' AS source,
            3 AS source_rank,
            te.id AS source_id,
            te.event_type AS event_type,
            te.created_at AS created_at,
            te.details AS summary,
            NULL AS payload_json,
            'system' AS actor,
            'task' AS entity_type,
            CAST(te.task_id AS TEXT) AS entity_id,
            NULL AS workflow_id,
            te.task_id AS task_id
        FROM task_events te
        JOIN tasks t ON t.id = te.task_id
        WHERE t.project_id = ?
    ) event_stream
"""


def _read_rows(
    project_id: int,
    cursor: EventCursor | None,
    *,
    limit: int,
    tail: bool,
):
    params: list[object] = [project_id, project_id, project_id]
    sql = _EVENT_STREAM_SQL

    if cursor is not None:
        sql += """
            WHERE (
                created_at > ?
                OR (
                    created_at = ?
                    AND (
                        source_rank > ?
                        OR (source_rank = ? AND source_id > ?)
                    )
                )
            )
            ORDER BY created_at ASC, source_rank ASC, source_id ASC
            LIMIT ?
        """
        params.extend(
            [
                cursor.created_at,
                cursor.created_at,
                cursor.source_rank,
                cursor.source_rank,
                cursor.source_id,
                limit + 1,
            ]
        )
    elif tail:
        sql += """
            ORDER BY created_at DESC, source_rank DESC, source_id DESC
            LIMIT ?
        """
        params.append(limit + 1)
    else:
        sql += """
            ORDER BY created_at ASC, source_rank ASC, source_id ASC
            LIMIT ?
        """
        params.append(limit + 1)

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    if tail:
        rows = list(reversed(rows))
    return rows


def list_nexus_events(
    project_id: int,
    *,
    after: str | None = None,
    limit: int = 100,
    tail: bool = False,
) -> dict:
    cursor = _decode_cursor(after)
    if cursor is not None:
        tail = False
    limit = max(1, min(int(limit), 250))

    rows = _read_rows(
        project_id,
        cursor,
        limit=limit,
        tail=bool(tail),
    )
    has_more = len(rows) > limit
    if has_more:
        if tail:
            rows = rows[-limit:]
        else:
            rows = rows[:limit]

    events: list[dict] = []
    for row in rows:
        item = dict(row)
        source = str(item["source"])
        if source == "task":
            payload = _task_payload(item.get("summary"))
            summary = (
                str(payload.get("message") or payload.get("details") or "").strip()
                or str(item["event_type"])
            )
        else:
            payload = _loads(item.get("payload_json"), {})
            if not isinstance(payload, dict):
                payload = {"value": payload}
            summary = str(item.get("summary") or item["event_type"])

        events.append(
            {
                "schema_version": NEXUS_EVENT_SCHEMA_VERSION,
                "id": f"{source}:{int(item['source_id'])}",
                "source": source,
                "source_id": int(item["source_id"]),
                "project_id": int(project_id),
                "event_type": str(item["event_type"]),
                "severity": _severity(str(item["event_type"])),
                "actor": str(item.get("actor") or "system"),
                "summary": summary,
                "payload": payload,
                "entity": {
                    "type": item.get("entity_type"),
                    "id": item.get("entity_id"),
                },
                "workflow_id": item.get("workflow_id"),
                "task_id": item.get("task_id"),
                "created_at": str(item["created_at"]),
                "requires_resync": True,
            }
        )

    next_cursor = after
    if events:
        last = events[-1]
        next_cursor = _encode_cursor(
            EventCursor(
                str(last["created_at"]),
                _SOURCE_RANK[str(last["source"])],
                int(last["source_id"]),
            )
        )

    return {
        "schema_version": NEXUS_EVENT_SCHEMA_VERSION,
        "events": events,
        "next_cursor": next_cursor,
        "has_more": bool(has_more and not tail),
        "tail": bool(tail),
        "resync": {
            "authoritative_source": "GET /api/projects/{project_id}/nexus",
            "required_after_events": True,
        },
    }
