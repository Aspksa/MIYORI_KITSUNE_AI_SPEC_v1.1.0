from __future__ import annotations

import unittest

from miyori.body_renderer import (
    BODY_RENDERER_SCHEMA_VERSION,
    build_body_renderer_contract,
    select_renderer_adapter,
)


class BodyRendererRegistryTests(unittest.TestCase):
    def test_character_rig_is_default_without_asset(self) -> None:
        appearance = {"asset": {"kind": None}}
        contract = build_body_renderer_contract(appearance)
        self.assertEqual(contract["schema_version"], BODY_RENDERER_SCHEMA_VERSION)
        self.assertEqual(contract["selected_adapter"], "trusted_character_rig")
        self.assertTrue(contract["selected_dynamic"])

    def test_static_portrait_remains_non_dynamic(self) -> None:
        appearance = {"asset": {"kind": "static_portrait"}}
        contract = build_body_renderer_contract(appearance)
        self.assertEqual(select_renderer_adapter(appearance), "static_portrait")
        self.assertFalse(contract["selected_dynamic"])

    def test_character_rig_is_installed_and_owner_aware(self) -> None:
        contract = build_body_renderer_contract({"asset": {"kind": None}})
        selected = next(item for item in contract["trusted_adapters"] if item["id"] == "trusted_character_rig")
        self.assertTrue(selected["installed"])
        self.assertTrue(selected["dynamic"])
        self.assertTrue(selected["supports"]["pose"])
        self.assertTrue(selected["supports"]["expression"])
        self.assertTrue(selected["supports"]["gesture"])
        self.assertTrue(contract["appearance_channels"]["owner_values_only"])
        self.assertEqual(contract["policy"]["appearance_source"], "owner_profile_only")
        self.assertTrue(contract["policy"]["unresolved_appearance_uses_neutral_visuals"])

    def test_unknown_asset_fails_closed_to_neutral_shell(self) -> None:
        contract = build_body_renderer_contract({"asset": {"kind": "invented_rig"}})
        self.assertEqual(contract["selected_adapter"], "neutral_shell")
        self.assertFalse(contract["selected_dynamic"])

    def test_dynamic_extension_is_character_rig_without_asset_code(self) -> None:
        extension = build_body_renderer_contract({"asset": {"kind": None}})["dynamic_extension"]
        self.assertEqual(extension["status"], "installed")
        self.assertEqual(extension["adapter_id"], "trusted_character_rig")
        self.assertEqual(extension["engine"], "trusted_dom_css_character_v1")
        self.assertFalse(extension["may_invent_owner_appearance_choices"])
        self.assertFalse(extension["may_execute_asset_javascript"])
        self.assertFalse(extension["may_override_operational_state"])


if __name__ == "__main__":
    unittest.main()
