from __future__ import annotations

import unittest

from miyori.context_router import route_context
from miyori.planner import fallback_decision, parse_planner_payload


class ContextRouterTests(unittest.TestCase):
    def test_small_talk_does_not_pull_project_data(self) -> None:
        route = route_context("Привет, как дела?")
        self.assertFalse(route.use_documents)
        self.assertFalse(route.use_project_memory)
        self.assertFalse(route.use_epistemic)
        self.assertFalse(route.use_tools)

    def test_document_lookup_routes_to_documents_and_tools(self) -> None:
        route = route_context("Найди договор с ООО Восток и проверь срок действия")
        self.assertTrue(route.use_documents)
        self.assertTrue(route.use_project_memory)
        self.assertTrue(route.use_epistemic)
        self.assertTrue(route.use_tools)

    def test_personal_preference_uses_user_memory(self) -> None:
        route = route_context("Какой интерфейс я предпочитаю?")
        self.assertTrue(route.use_user_memory)
        self.assertFalse(route.use_documents)

    def test_explicit_document_opt_out_wins(self) -> None:
        route = route_context("Ответь без документов: что такое договор?")
        self.assertFalse(route.use_documents)

    def test_fallback_prioritizes_explicit_write(self) -> None:
        route = route_context('Создай папку «Договоры 2027»')
        decision = fallback_decision('Создай папку «Договоры 2027»', route, [])
        self.assertEqual(decision.action, "tool")
        self.assertEqual(decision.tool_name, "drive_folder_create")
        self.assertEqual(decision.arguments["name"], "Договоры 2027")

    def test_planner_cannot_invent_tool(self) -> None:
        with self.assertRaises(ValueError):
            parse_planner_payload(
                {
                    "action": "tool",
                    "tool_name": "unsafe_magic",
                    "arguments": {},
                    "reason": "test",
                },
                {"project_status"},
            )


if __name__ == "__main__":
    unittest.main()
