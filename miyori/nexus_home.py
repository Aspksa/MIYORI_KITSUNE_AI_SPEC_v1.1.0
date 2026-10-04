from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

from .db import (
    connect,
    get_project,
    list_home_devices,
    list_parental_profiles,
    record_audit_event,
    utc_now,
)


NEXUS_HOME_SCHEMA_VERSION = "1.0.0"
HOME_HEARTBEAT_TTL_SECONDS = 180
HOME_LINK_STATES = {"unlinked", "linked", "revoked"}
HOME_CAPABILITIES = {
    "presence",
    "network_status",
    "notifications",
    "screen_time",
    "parental_policy",
}


def init_nexus_home_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS home_device_runtime (
                device_id INTEGER PRIMARY KEY,
                identity_hash TEXT,
                link_status TEXT NOT NULL DEFAULT 'unlinked'
                    CHECK(link_status IN ('unlinked','linked','revoked')),
                capabilities_json TEXT NOT NULL DEFAULT '[]',
                reported_state_json TEXT NOT NULL DEFAULT '{}',
                heartbeat_seq INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT,
                linked_at TEXT,
                revoked_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES home_devices(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS home_parental_bindings (
                profile_id INTEGER PRIMARY KEY,
                device_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES parental_control_profiles(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES home_devices(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_home_runtime_status
                ON home_device_runtime(link_status, last_seen_at DESC);
            CREATE INDEX IF NOT EXISTS idx_home_parental_device
                ON home_parental_bindings(device_id);
            """
        )


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _credential_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _project(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")
    return project


def _home_project(project_id: int) -> dict:
    project = _project(project_id)
    if project.get("kind") != "home":
        raise ValueError("Home capability доступен только для домашнего проекта.")
    return project


def _device(project_id: int, device_id: int) -> dict:
    for item in list_home_devices(project_id):
        if int(item["id"]) == int(device_id):
            return item
    raise ValueError("Домашнее устройство не найдено в текущем проекте.")


def _runtime_rows(device_ids: list[int]) -> dict[int, dict]:
    if not device_ids:
        return {}
    placeholders = ",".join("?" for _ in device_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM home_device_runtime
            WHERE device_id IN ({placeholders})
            """,
            device_ids,
        ).fetchall()
    result: dict[int, dict] = {}
    for row in rows:
        item = dict(row)
        item["capabilities"] = list(_loads(item.pop("capabilities_json", None), []))
        item["reported_state"] = dict(_loads(item.pop("reported_state_json", None), {}))
        result[int(item["device_id"])] = item
    return result


def _connectivity(runtime: dict | None, *, now: datetime | None = None) -> dict:
    current = now or _now()
    if not runtime:
        return {
            "state": "unlinked",
            "online": False,
            "freshness_seconds": None,
            "last_seen_at": None,
            "heartbeat_seq": 0,
        }
    link_status = str(runtime.get("link_status") or "unlinked")
    if link_status != "linked":
        return {
            "state": "revoked" if link_status == "revoked" else "unlinked",
            "online": False,
            "freshness_seconds": None,
            "last_seen_at": runtime.get("last_seen_at"),
            "heartbeat_seq": int(runtime.get("heartbeat_seq") or 0),
        }
    seen = _parse_time(runtime.get("last_seen_at"))
    if not seen:
        return {
            "state": "never_seen",
            "online": False,
            "freshness_seconds": None,
            "last_seen_at": None,
            "heartbeat_seq": int(runtime.get("heartbeat_seq") or 0),
        }
    freshness = max(0, int((current - seen).total_seconds()))
    online = freshness <= HOME_HEARTBEAT_TTL_SECONDS
    return {
        "state": "online" if online else "offline",
        "online": online,
        "freshness_seconds": freshness,
        "last_seen_at": runtime.get("last_seen_at"),
        "heartbeat_seq": int(runtime.get("heartbeat_seq") or 0),
    }


def _binding_rows(profile_ids: list[int]) -> dict[int, int]:
    if not profile_ids:
        return {}
    placeholders = ",".join("?" for _ in profile_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT profile_id, device_id
            FROM home_parental_bindings
            WHERE profile_id IN ({placeholders})
            """,
            profile_ids,
        ).fetchall()
    return {int(row["profile_id"]): int(row["device_id"]) for row in rows}


def build_nexus_home(project_id: int) -> dict:
    init_nexus_home_db()
    project = _project(project_id)
    enabled = project.get("kind") == "home"
    devices = list_home_devices(project_id)
    runtimes = _runtime_rows([int(item["id"]) for item in devices])
    now = _now()

    device_items: list[dict] = []
    online_count = 0
    linked_count = 0
    for item in devices:
        device_id = int(item["id"])
        runtime = runtimes.get(device_id)
        connectivity = _connectivity(runtime, now=now)
        capabilities = list((runtime or {}).get("capabilities") or [])
        link_status = str((runtime or {}).get("link_status") or "unlinked")
        if link_status == "linked":
            linked_count += 1
        if connectivity["online"]:
            online_count += 1
        device_items.append(
            {
                "id": device_id,
                "name": item["name"],
                "device_type": item.get("device_type") or "device",
                "address": item.get("address") or "",
                "declared_status": item.get("status") or "offline",
                "notes": item.get("notes") or "",
                "link_status": link_status,
                "capabilities": capabilities,
                "connectivity": connectivity,
                "reported_state": dict((runtime or {}).get("reported_state") or {}),
                "linked_at": (runtime or {}).get("linked_at"),
                "updated_at": item.get("updated_at"),
                "actions": {
                    "can_link": enabled and link_status != "linked",
                    "can_unlink": enabled and link_status == "linked",
                },
            }
        )

    profiles = list_parental_profiles(project_id)
    bindings = _binding_rows([int(item["id"]) for item in profiles])
    device_by_id = {int(item["id"]): item for item in device_items}
    profile_items: list[dict] = []
    parental_attention = 0
    for profile in profiles:
        profile_id = int(profile["id"])
        device_id = bindings.get(profile_id)
        device = device_by_id.get(int(device_id)) if device_id else None
        linked = bool(device and device.get("link_status") == "linked")
        has_capability = bool(device and "parental_policy" in (device.get("capabilities") or []))
        online = bool(device and (device.get("connectivity") or {}).get("online"))

        if not device_id:
            enforcement = "not_bound"
        elif not linked:
            enforcement = "device_not_linked"
        elif not has_capability:
            enforcement = "capability_missing"
        elif not online:
            enforcement = "device_offline"
        else:
            enforcement = "ready_for_device_agent"

        if str(profile.get("status") or "") != "draft" and enforcement != "ready_for_device_agent":
            parental_attention += 1

        profile_items.append(
            {
                **profile,
                "binding": {
                    "device_id": device_id,
                    "device_name": device.get("name") if device else None,
                    "explicitly_linked": linked,
                    "enforcement_state": enforcement,
                    "applied": False,
                    "note": (
                        "Правила подготовлены для device-agent, но этот релиз не заявляет OS-level enforcement."
                    ),
                },
            }
        )

    stale_linked = max(0, linked_count - online_count)
    return {
        "schema_version": NEXUS_HOME_SCHEMA_VERSION,
        "project": {
            "id": int(project["id"]),
            "name": project["name"],
            "kind": project.get("kind"),
        },
        "enabled": enabled,
        "devices": device_items,
        "parental_profiles": profile_items,
        "counts": {
            "devices": len(device_items),
            "linked": linked_count,
            "online": online_count,
            "offline_or_unseen": stale_linked,
            "parental_profiles": len(profile_items),
            "parental_attention": parental_attention,
        },
        "policy": {
            "connectivity_source": "authenticated_heartbeat",
            "legacy_status_is_connectivity_source": False,
            "heartbeat_ttl_seconds": HOME_HEARTBEAT_TTL_SECONDS,
            "network_scanning_enabled": False,
            "unknown_device_auto_link_allowed": False,
            "parental_rules_require_explicit_binding": True,
            "parental_rules_applied_by_server": False,
            "device_commands_enabled": False,
        },
        "generated_at": utc_now(),
    }


def link_home_device(
    project_id: int,
    device_id: int,
    *,
    capabilities: list[str] | None = None,
) -> dict:
    init_nexus_home_db()
    _home_project(project_id)
    device = _device(project_id, device_id)
    requested = sorted({str(value).strip() for value in (capabilities or []) if str(value).strip()})
    unknown = set(requested) - HOME_CAPABILITIES
    if unknown:
        raise ValueError("Неизвестные Home capabilities: " + ", ".join(sorted(unknown)))

    credential = secrets.token_urlsafe(32)
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO home_device_runtime(
                device_id, identity_hash, link_status, capabilities_json,
                reported_state_json, heartbeat_seq, last_seen_at,
                linked_at, revoked_at, updated_at
            ) VALUES (?, ?, 'linked', ?, '{}', 0, NULL, ?, NULL, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                identity_hash = excluded.identity_hash,
                link_status = 'linked',
                capabilities_json = excluded.capabilities_json,
                reported_state_json = '{}',
                heartbeat_seq = 0,
                last_seen_at = NULL,
                linked_at = excluded.linked_at,
                revoked_at = NULL,
                updated_at = excluded.updated_at
            """,
            (
                device_id,
                _credential_hash(credential),
                json.dumps(requested, ensure_ascii=False),
                now,
                now,
            ),
        )
    record_audit_event(
        project_id,
        "user",
        "home.device_linked",
        f"Устройство «{device['name']}» явно привязано к Home.",
        entity_type="home_device",
        entity_id=device_id,
        details={"capabilities": requested},
    )
    return {
        "device_id": device_id,
        "credential": credential,
        "credential_exposed_once": True,
        "home": build_nexus_home(project_id),
    }


def unlink_home_device(project_id: int, device_id: int) -> dict:
    init_nexus_home_db()
    _home_project(project_id)
    device = _device(project_id, device_id)
    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT device_id FROM home_device_runtime WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            raise ValueError("Устройство ещё не было привязано.")
        conn.execute(
            """
            UPDATE home_device_runtime
            SET identity_hash = NULL, link_status = 'revoked',
                revoked_at = ?, updated_at = ?
            WHERE device_id = ?
            """,
            (now, now, device_id),
        )
    record_audit_event(
        project_id,
        "user",
        "home.device_unlinked",
        f"Привязка устройства «{device['name']}» отозвана.",
        entity_type="home_device",
        entity_id=device_id,
    )
    return build_nexus_home(project_id)


def record_home_heartbeat(
    project_id: int,
    device_id: int,
    *,
    credential: str,
    capabilities: list[str] | None = None,
    reported_state: dict | None = None,
) -> dict:
    init_nexus_home_db()
    _home_project(project_id)
    device = _device(project_id, device_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM home_device_runtime WHERE device_id = ?",
            (device_id,),
        ).fetchone()
    if not row or row["link_status"] != "linked" or not row["identity_hash"]:
        raise ValueError("Устройство не имеет активной Home-привязки.")
    if not secrets.compare_digest(str(row["identity_hash"]), _credential_hash(credential)):
        raise PermissionError("Heartbeat credential не соответствует устройству.")

    previous = dict(row)
    previous["capabilities"] = list(_loads(previous.get("capabilities_json"), []))
    was_online = _connectivity(previous)["online"]

    requested = (
        sorted({str(value).strip() for value in capabilities if str(value).strip()})
        if capabilities is not None
        else list(previous["capabilities"])
    )
    unknown = set(requested) - HOME_CAPABILITIES
    if unknown:
        raise ValueError("Неизвестные Home capabilities: " + ", ".join(sorted(unknown)))

    state = dict(reported_state or {})
    if len(json.dumps(state, ensure_ascii=False, default=str)) > 8000:
        raise ValueError("Heartbeat state слишком большой.")

    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE home_device_runtime
            SET capabilities_json = ?, reported_state_json = ?,
                heartbeat_seq = heartbeat_seq + 1,
                last_seen_at = ?, updated_at = ?
            WHERE device_id = ?
            """,
            (
                json.dumps(requested, ensure_ascii=False),
                json.dumps(state, ensure_ascii=False, default=str),
                now,
                now,
                device_id,
            ),
        )
    if not was_online:
        record_audit_event(
            project_id,
            "system",
            "home.device_online",
            f"Получен подтверждённый heartbeat устройства «{device['name']}».",
            entity_type="home_device",
            entity_id=device_id,
            details={"capabilities": requested},
        )
    return build_nexus_home(project_id)


def bind_parental_profile(
    project_id: int,
    profile_id: int,
    device_id: int,
) -> dict:
    init_nexus_home_db()
    _home_project(project_id)
    device = _device(project_id, device_id)
    profiles = {int(item["id"]): item for item in list_parental_profiles(project_id)}
    profile = profiles.get(int(profile_id))
    if not profile:
        raise ValueError("Профиль родительского контроля не найден.")

    runtime = _runtime_rows([device_id]).get(device_id)
    if not runtime or runtime.get("link_status") != "linked":
        raise ValueError("Parental profile можно привязать только к явно связанному устройству.")
    capabilities = set(runtime.get("capabilities") or [])
    if "parental_policy" not in capabilities:
        raise ValueError("Устройство не заявило capability parental_policy.")

    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO home_parental_bindings(profile_id, device_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET
                device_id = excluded.device_id,
                updated_at = excluded.updated_at
            """,
            (profile_id, device_id, now, now),
        )
    record_audit_event(
        project_id,
        "user",
        "home.parental_profile_bound",
        f"Профиль «{profile['child_name']}» привязан к «{device['name']}».",
        entity_type="parental_control_profile",
        entity_id=profile_id,
        details={"device_id": device_id},
    )
    return build_nexus_home(project_id)
