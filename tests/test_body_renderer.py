from __future__ import annotations

import unittest

from miyori.body_renderer import (
    BODY_RENDERER_SCHEMA_VERSION,
    build_body_renderer_contract,
    select_renderer_adapter,
)


class BodyRendererRegistryTests(unittest.TestCase):
    def test_trusted_vector_rig_is_default_without_asset(self) -> None:
        appearance = {"asset": {"kind": None}}
        contract = build_body_renderer_contract(appearance)
        self.assertEqual(contract["schema_version"], BODY_RENDERER_SCHEMA_VERSION)
        self.assertEqual(contract["selected_adapter"], "trusted_vector_rig")
        self.assertTrue(contract["selected_dynamic"])

    def test_static_portrait_is_selected_but_never_claimed_dynamic(self) -> None:
        appearance = {"asset": {"kind": "static_portrait"}}
        contract = build_body_renderer_contract(appearance)
        self.assertEqual(select_renderer_adapter(appearance), "static_portrait")
        self.assertEqual(contract["selected_adapter"], "static_portrait")
        self.assertFalse(contract["selected_dynamic"])
        selected = next(
            item
            for item in contract["trusted_adapters"]
            if item["id"] == "static_portrait"
        )
        self.assertFalse(selected["dynamic"])
        self.assertFalse(selected["supports"]["pose"])
        self.assertFalse(selected["supports"]["expression"])
        self.assertFalse(selected["supports"]["gesture"])

    def test_trusted_vector_rig_consumes_all_presentation_channels(self) -> None:
        contract = build_body_renderer_contract({"asset": {"kind": None}})
        selected = next(
            item
            for item in contract["trusted_adapters"]
            if item["id"] == "trusted_vector_rig"
        )
        self.assertTrue(selected["installed"])
        self.assertTrue(selected["dynamic"])
        self.assertTrue(selected["supports"]["pose"])
        self.assertTrue(selected["supports"]["expression"])
        self.assertTrue(selected["supports"]["gesture"])

    def test_unknown_asset_fails_closed_to_neutral_shell(self) -> None:
        contract = build_body_renderer_contract({"asset": {"kind": "invented_rig"}})
        self.assertEqual(contract["selected_adapter"], "neutral_shell")
        self.assertFalse(contract["selected_dynamic"])
        self.assertEqual(
            contract["policy"]["unknown_adapter_fallback"],
            "neutral_shell",
        )

    def test_dynamic_extension_is_installed_without_asset_code_execution(self) -> None:
        contract = build_body_renderer_contract({"asset": {"kind": None}})
        extension = contract["dynamic_extension"]
        self.assertEqual(extension["status"], "installed")
        self.assertEqual(extension["adapter_id"], "trusted_vector_rig")
        self.assertEqual(extension["engine"], "trusted_dom_css_vector_v1")
        self.assertTrue(extension["adapter_contract_required"])
        self.assertTrue(extension["must_be_trusted_registry_entry"])
        self.assertTrue(extension["must_consume_existing_presentation_channels"])
        self.assertFalse(extension["may_invent_owner_appearance_choices"])
        self.assertFalse(extension["may_execute_asset_javascript"])
        self.assertFalse(extension["may_override_operational_state"])

    def test_registry_forbids_arbitrary_renderer_code(self) -> None:
        policy = build_body_renderer_contract({"asset": {"kind": None}})["policy"]
        self.assertTrue(policy["trusted_registry_only"])
        self.assertFalse(policy["arbitrary_renderer_module_allowed"])
        self.assertFalse(policy["asset_authored_javascript_allowed"])
        self.assertFalse(policy["model_select_adapter_allowed"])
        self.assertTrue(policy["dynamic_renderer_claim_requires_installed_adapter"])
        self.assertEqual(
            policy["dynamic_motion_source"],
            "versioned_presentation_channels_only",
        )


if __name__ == "__main__":
    unittest.main()
