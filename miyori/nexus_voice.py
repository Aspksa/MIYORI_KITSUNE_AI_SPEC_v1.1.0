from __future__ import annotations

from datetime import datetime, timezone

from .db import get_project


NEXUS_VOICE_SCHEMA_VERSION = "1.0.0"
VOICE_STATES = (
    "unavailable",
    "idle",
    "listening",
    "transcribing",
    "thinking",
    "speaking",
    "interrupted",
    "error",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_nexus_voice_contract(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")

    return {
        "schema_version": NEXUS_VOICE_SCHEMA_VERSION,
        "project": {
            "id": int(project["id"]),
            "name": project["name"],
            "kind": project.get("kind"),
        },
        "protocol": {
            "states": list(VOICE_STATES),
            "default_state": "idle",
            "final_transcript_required_before_submit": True,
            "interim_transcript_is_ephemeral": True,
            "confidence_is_advisory": True,
            "barge_in_allowed": True,
            "cancel_allowed": True,
        },
        "permissions": {
            "microphone_requires_explicit_user_gesture": True,
            "microphone_permission_must_be_browser_or_os_managed": True,
            "background_recording_allowed": False,
        },
        "safety": {
            "voice_can_bypass_action_permissions": False,
            "voice_can_auto_approve_actions": False,
            "voice_can_auto_execute_write_tools": False,
            "final_transcript_uses_existing_chat_pipeline": True,
        },
        "transport": {
            "browser_recognition": "optional",
            "browser_tts": "optional",
            "desktop_transport_replaceable": True,
            "server_audio_storage": False,
        },
        "generated_at": _now(),
    }
