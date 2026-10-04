from __future__ import annotations

from typing import Any


BODY_RENDERER_SCHEMA_VERSION = "1.2.0"

_TRUSTED_ADAPTERS = (
    {
        "id": "neutral_shell",
        "label": "Neutral shell",
        "installed": True,
        "dynamic": False,
        "requires_asset_kind": None,
        "supports": {"pose": True, "expression": True, "gesture": True},
        "semantics": "Минимальная fail-closed оболочка без owner appearance choices.",
    },
    {
        "id": "static_portrait",
        "label": "Static portrait",
        "installed": True,
        "dynamic": False,
        "requires_asset_kind": "static_portrait",
        "supports": {"pose": False, "expression": False, "gesture": False},
        "semantics": "Пользовательское изображение остаётся неподвижным.",
    },
    {
        "id": "trusted_vector_rig",
        "label": "Trusted vector rig",
        "installed": True,
        "dynamic": True,
        "requires_asset_kind": None,
        "supports": {"pose": True, "expression": True, "gesture": True},
        "semantics": "Нейтральный vector rig предыдущего поколения сохраняется как trusted fallback.",
    },
    {
        "id": "trusted_character_rig",
        "label": "Miyori character rig",
        "installed": True,
        "dynamic": True,
        "requires_asset_kind": None,
        "supports": {"pose": True, "expression": True, "gesture": True},
        "semantics": (
            "Полнофигурный trusted character rig отображает подтверждённые черты "
            "Миёри: лицо, волосы как нейтральную форму, лисьи ушки, тело, руки и "
            "одежду как нейтральный силуэт. Точный цвет волос/глаз, число хвостов "
            "и основной наряд применяются только из owner Appearance Profile."
        ),
    },
)


def _asset_kind(appearance: dict[str, Any]) -> str | None:
    asset = appearance.get("asset")
    if not isinstance(asset, dict):
        return None
    raw = str(asset.get("kind") or "").strip()
    return raw or None


def select_renderer_adapter(appearance: dict[str, Any]) -> str:
    kind = _asset_kind(appearance)
    if kind == "static_portrait":
        return "static_portrait"
    if kind is None:
        return "trusted_character_rig"
    return "neutral_shell"


def build_body_renderer_contract(appearance: dict[str, Any]) -> dict:
    selected = select_renderer_adapter(appearance)
    adapters = [dict(item) for item in _TRUSTED_ADAPTERS]
    selected_item = next(item for item in adapters if item["id"] == selected)

    return {
        "schema_version": BODY_RENDERER_SCHEMA_VERSION,
        "selected_adapter": selected,
        "selected_dynamic": bool(selected_item["dynamic"]),
        "trusted_adapters": adapters,
        "presentation_channels": {
            "pose": "body.presentation.pose",
            "expression": "body.presentation.expression",
            "gesture": "body.presentation.gesture",
            "state": "body.state_or_explicit_local_runtime",
        },
        "appearance_channels": {
            "hair_color": "body.appearance.selections.hair_color",
            "eye_color": "body.appearance.selections.eye_color",
            "tail_count": "body.appearance.selections.tail_count",
            "main_outfit": "body.appearance.selections.main_outfit",
            "owner_values_only": True,
        },
        "dynamic_extension": {
            "status": "installed",
            "adapter_id": "trusted_character_rig",
            "engine": "trusted_dom_css_character_v1",
            "asset_requirement": "owner_choice_aware_builtin_character",
            "adapter_contract_required": True,
            "must_be_trusted_registry_entry": True,
            "must_consume_existing_presentation_channels": True,
            "may_invent_owner_appearance_choices": False,
            "may_execute_asset_javascript": False,
            "may_override_operational_state": False,
        },
        "policy": {
            "trusted_registry_only": True,
            "arbitrary_renderer_module_allowed": False,
            "asset_authored_javascript_allowed": False,
            "model_select_adapter_allowed": False,
            "unknown_adapter_fallback": "neutral_shell",
            "static_portrait_is_dynamic": False,
            "dynamic_renderer_claim_requires_installed_adapter": True,
            "dynamic_motion_source": "versioned_presentation_channels_only",
            "appearance_source": "owner_profile_only",
            "unresolved_appearance_uses_neutral_visuals": True,
        },
    }
