from __future__ import annotations

from datetime import datetime, timezone

from .appearance import get_appearance_profile
from .body_renderer import build_body_renderer_contract
from .nexus_presence import build_nexus_presence
from .persona import load_persona_corpus


NEXUS_BODY_SCHEMA_VERSION = "1.3.0"
NEXUS_BODY_STATES = (
    "ready",
    "working",
    "verifying",
    "waiting",
    "recovery",
    "attention",
    "degraded",
)
NEXUS_BODY_LOCAL_STATES = (
    "idle",
    "thinking",
    "listening",
    "transcribing",
    "speaking",
    "interrupted",
    "voice_error",
)

_BODY_PRESENTATION = {
    "ready": {
        "pose": "rest",
        "expression": "neutral",
        "gesture": "still",
        "label": "Готова",
    },
    "working": {
        "pose": "focus",
        "expression": "focused",
        "gesture": "working",
        "label": "Работаю",
    },
    "verifying": {
        "pose": "inspect",
        "expression": "focused",
        "gesture": "verify",
        "label": "Проверяю",
    },
    "waiting": {
        "pose": "listen",
        "expression": "attentive",
        "gesture": "hold",
        "label": "Жду решения",
    },
    "recovery": {
        "pose": "inspect",
        "expression": "alert",
        "gesture": "recover",
        "label": "Восстанавливаю",
    },
    "attention": {
        "pose": "alert",
        "expression": "alert",
        "gesture": "attention",
        "label": "Нужно внимание",
    },
    "degraded": {
        "pose": "restrained",
        "expression": "neutral",
        "gesture": "limited",
        "label": "Есть ограничения",
    },
}

_LOCAL_PRESENTATION = {
    "idle": None,
    "thinking": {
        "pose": "focus",
        "expression": "focused",
        "gesture": "thinking",
        "label": "Думаю",
    },
    "listening": {
        "pose": "listen",
        "expression": "attentive",
        "gesture": "listen",
        "label": "Слушаю",
    },
    "transcribing": {
        "pose": "focus",
        "expression": "attentive",
        "gesture": "transcribe",
        "label": "Распознаю",
    },
    "speaking": {
        "pose": "speak",
        "expression": "calm",
        "gesture": "speak",
        "label": "Говорю",
    },
    "interrupted": {
        "pose": "rest",
        "expression": "neutral",
        "gesture": "pause",
        "label": "Голос остановлен",
    },
    "voice_error": {
        "pose": "alert",
        "expression": "alert",
        "gesture": "attention",
        "label": "Проблема с голосом",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persona_appearance() -> dict:
    corpus = load_persona_corpus()
    identity = corpus.get("identity") or {}
    confirmed = [
        str(value)
        for value in (identity.get("appearance_confirmed") or [])
        if str(value).strip()
    ]
    open_choices = [
        str(value)
        for value in (identity.get("appearance_open_for_user_choice") or [])
        if str(value).strip()
    ]
    profile = get_appearance_profile()
    return {
        "persona_version": str(corpus.get("content_version") or ""),
        "name": str(identity.get("name") or "Миёри"),
        "nickname": str(identity.get("nickname") or "Миё"),
        "age_years": int(identity.get("age_years") or 0),
        "is_adult": bool(identity.get("is_adult")),
        "species": str(identity.get("species") or ""),
        "confirmed": confirmed,
        "open_for_owner_choice": open_choices,
        "configuration_state": profile["state"],
        "final_portrait_asset": profile["asset"]["url"],
        "selections": profile["selection"],
        "asset": profile["asset"],
        "appearance_profile_schema_version": profile["schema_version"],
        "appearance_revision": profile["revision"],
    }


def _body_state_from_presence(presence: dict) -> str:
    mode = str(presence.get("mode") or "ready")
    if mode not in NEXUS_BODY_STATES:
        return "degraded"
    return mode


def build_nexus_body(project_id: int) -> dict:
    presence = build_nexus_presence(project_id)
    state = _body_state_from_presence(presence)
    presentation = dict(_BODY_PRESENTATION[state])
    appearance = _persona_appearance()
    renderer = build_body_renderer_contract(appearance)

    return {
        "schema_version": NEXUS_BODY_SCHEMA_VERSION,
        "project": presence["project"],
        "state": state,
        "presentation": presentation,
        "appearance": appearance,
        "renderer": renderer,
        "runtime": {
            "presence_mode": presence.get("mode"),
            "presence_attention": presence.get("attention"),
            "headline": presence.get("headline"),
            "detail": presence.get("detail"),
            "source": "nexus_presence",
        },
        "local_override_contract": {
            "allowed_states": list(NEXUS_BODY_LOCAL_STATES),
            "presentations": {
                key: value
                for key, value in _LOCAL_PRESENTATION.items()
                if value is not None
            },
            "idle_returns_to_server_state": True,
            "voice_state_source": "miyori:voice-state",
            "thinking_state_source": "miyori:interaction-state",
        },
        "motion_policy": {
            "random_liveness_allowed": False,
            "timer_idle_animation_allowed": False,
            "sentiment_to_expression_allowed": False,
            "model_authored_motion_allowed": False,
            "state_transition_motion_allowed": True,
            "contract_driven_active_motion_allowed": True,
            "reduced_motion_must_be_respected": True,
        },
        "render_policy": {
            "neutral_shell_until_owner_appearance_choice": True,
            "owner_global_appearance_profile": True,
            "static_portrait_is_non_dynamic": True,
            "trusted_vector_rig_installed": True,
            "dynamic_renderer_may_invent_appearance": False,
            "invent_open_appearance_choices_allowed": False,
            "tail_count_may_be_invented": False,
            "hair_color_may_be_invented": False,
            "eye_color_may_be_invented": False,
            "outfit_may_be_invented": False,
            "body_state_source": "presence_plus_explicit_local_runtime",
        },
        "generated_at": _now(),
    }
