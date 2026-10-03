from __future__ import annotations

import unittest

from miyori.persona import build_persona_context, load_persona_corpus, persona_metadata


class PersonaPackTests(unittest.TestCase):
    def test_corpus_metadata(self) -> None:
        metadata = persona_metadata()
        self.assertEqual(metadata["version"], "2.0.0")
        self.assertEqual(metadata["biography_sections"], 24)
        self.assertEqual(metadata["phrases"], 700)
        self.assertEqual(metadata["dialogues"], 300)

    def test_corpus_is_full_and_not_user_history(self) -> None:
        data = load_persona_corpus()
        self.assertEqual(len(data["biography"]["sections"]), 24)
        self.assertEqual(len(data["phrase_library"]["entries"]), 700)
        self.assertEqual(len(data["dialogue_library"]["entries"]), 300)
        self.assertTrue(all(item.get("is_user_history") is False for item in data["dialogue_library"]["entries"]))

    def test_context_is_compact_and_persona_grounded(self) -> None:
        context = build_persona_context([
            {"role": "user", "content": "Миёри, расскажи о своём характере."}
        ])
        self.assertIn("КАНОНИЧЕСКАЯ ЛИЧНОСТЬ МИЁРИ", context)
        self.assertIn("Persona Pack v2.0.0", context)
        self.assertIn("Художественная биография Миёри не является историей пользователя", context)
        self.assertLess(len(context), 8000)


if __name__ == "__main__":
    unittest.main()
