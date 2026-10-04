from __future__ import annotations

from typing import Any


BODY_RENDERER_SCHEMA_VERSION = "1.0.0"

_TRUSTED_ADAPTERS = (
    {
        "id": "neutral_shell",
        "label": "Neutral shell",
        "installed": True,
        "dynamic": False,
        "requires_asset_kind": None,
        "supports": {
            "pose": True,
            "expression": True,
            "gesture": True,
        },
        "semantics": (
            "CSS-примитивы отображают только contract pose/expression/gesture "
            "и не фиксируют открытые owner appearance choices."
        ),
    },
    {
        "id": "static_portrait",
        "label": "Static portrait",
        "installed": True,
        "dynamic": False,
        "requires_asset_kind": "static_portrait",
        "supports": {
            "pose": False,
            "expression": False,
            "gesture": False,
        },
        "semantics": (
            "Пользовательское изображение остаётся неподвижным; runtime state "
            "показывается отдельным индикатором и подписью."
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
    if _asset_kind(appearance) == "static_portrait":
        return "static_portrait"
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
        "dynamic_extension": {
            "status": "not_installed",
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
        },
    }
