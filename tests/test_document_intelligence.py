from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from miyori.config import settings
from miyori.db import (
    add_document,
    claim_next_task,
    create_project,
    create_task,
    init_db,
    mark_interrupted_runtime_for_recovery,
)
from miyori.document_intelligence import (
    build_local_document_intelligence,
    deep_analyze_document,
    document_context_packet,
    get_document_intelligence,
    get_document_nodes,
    init_document_intelligence_db,
    search_document_nodes,
)
from miyori.documents import (
    chunk_text,
    extract_structured_document,
    save_original,
    sha256_bytes,
)
from miyori.rag import init_rag, retrieve
from miyori.tools import list_tools


class DocumentIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        self.project = create_project("Document Intelligence Test", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _store(self, filename: str, data: bytes) -> tuple[dict, object]:
        structured = extract_structured_document(filename, data)
        digest = sha256_bytes(data)
        stored = save_original(self.project_id, filename, data, digest)
        document = add_document(
            self.project_id,
            filename,
            stored,
            "text/markdown" if filename.endswith(".md") else "text/plain",
            digest,
            len(data),
            chunk_text(structured.text),
        )
        return document, structured

    def test_markdown_structure_preserves_outline_and_locators(self) -> None:
        data = (
            "# Руководство Miyori\n\n"
            "Введение в систему.\n\n"
            "## Глава 1. Архитектура\n\n"
            "Первый раздел описывает ядро.\n\n"
            "### 1.1 Workflow\n\n"
            "Workflow сохраняется в SQLite.\n"
        ).encode("utf-8")
        document, structured = self._store("guide.md", data)
        profile = build_local_document_intelligence(
            self.project_id,
            int(document["id"]),
            structured,
        )

        self.assertEqual(profile["status"], "indexed")
        self.assertGreaterEqual(profile["section_count"], 3)
        self.assertEqual(profile["coverage_ratio"], 0.0)
        titles = [item["title"] for item in profile["outline"]]
        self.assertIn("Руководство Miyori", titles)
        self.assertIn("Глава 1. Архитектура", titles)
        self.assertTrue(all(item["locator"] for item in profile["outline"]))

        nodes = get_document_nodes(self.project_id, int(document["id"]), limit=100)
        self.assertGreaterEqual(len(nodes), 6)
        self.assertTrue(any(node["level"] == 3 for node in nodes if node["node_type"] == "heading"))

    def test_structural_search_returns_match_and_neighbors(self) -> None:
        data = (
            "# Книга\n\n"
            "Вступление.\n\n"
            "## Договоры\n\n"
            "Срок действия договора составляет один год.\n\n"
            "Следующий абзац описывает продление и уведомление.\n\n"
            "## Финал\n\n"
            "Заключение."
        ).encode("utf-8")
        document, structured = self._store("book.md", data)
        build_local_document_intelligence(self.project_id, int(document["id"]), structured)

        nodes = search_document_nodes(
            self.project_id,
            int(document["id"]),
            "срок действия договора",
            limit=4,
            neighbor_radius=1,
        )
        self.assertTrue(any(item["matched"] for item in nodes))
        self.assertTrue(any("договор" in item["text"].lower() for item in nodes))

        packet = document_context_packet(
            self.project_id,
            int(document["id"]),
            "продление договора",
        )
        self.assertEqual(packet["document_id"], int(document["id"]))
        self.assertTrue(packet["outline"])
        self.assertTrue(packet["matches"])

    def test_deep_analysis_covers_entire_long_document_and_resumes_windows(self) -> None:
        chapters = []
        for index in range(1, 16):
            body = (
                f"Глава {index} описывает контрольный процесс {index}. "
                + ("Подробное содержание раздела и проверяемые факты. " * 140)
            )
            chapters.append(f"## Глава {index}\n\n{body}")
        data = ("# Большая книга\n\n" + "\n\n".join(chapters)).encode("utf-8")

        document, structured = self._store("large-book.md", data)
        build_local_document_intelligence(self.project_id, int(document["id"]), structured)

        async def fake_window(title, index, total, content):
            locator = content.split("]", 1)[0].lstrip("[")
            return {
                "summary": f"Окно {index} из {total}",
                "key_points": [{"text": f"Факт окна {index}", "locator": locator}],
                "entities": [],
                "obligations": [],
                "dates": [],
                "amounts": [],
                "definitions": [],
                "risks": [],
                "themes": ["контроль"],
                "open_questions": [],
            }

        async def fake_synthesis(title, analyses, level=1):
            return {
                "summary_short": "Книга полностью проанализирована.",
                "summary_long": "Сводка построена из всех последовательно прочитанных окон документа.",
                "key_points": [],
                "entities": [],
                "obligations": [],
                "dates": [],
                "amounts": [],
                "definitions": [],
                "risks": [],
                "themes": ["контроль"],
                "open_questions": [],
                "contradictions": [],
            }

        window_mock = AsyncMock(side_effect=fake_window)
        synth_mock = AsyncMock(side_effect=fake_synthesis)
        with patch(
            "miyori.document_intelligence.analyze_document_window",
            window_mock,
        ), patch(
            "miyori.document_intelligence.synthesize_document_analysis",
            synth_mock,
        ):
            first = asyncio.run(
                deep_analyze_document(self.project_id, int(document["id"]))
            )
            calls_after_first = window_mock.await_count
            self.assertGreater(calls_after_first, 2)
            self.assertEqual(first["status"], "complete")
            self.assertGreaterEqual(first["coverage_ratio"], 0.995)
            self.assertEqual(first["windows_completed"], first["windows_total"])

            second = asyncio.run(
                deep_analyze_document(self.project_id, int(document["id"]))
            )
            self.assertEqual(window_mock.await_count, calls_after_first)
            self.assertEqual(second["status"], "complete")
            self.assertGreaterEqual(second["coverage_ratio"], 0.995)

        profile = get_document_intelligence(self.project_id, int(document["id"]))
        self.assertEqual(profile["summary_short"], "Книга полностью проанализирована.")
        self.assertGreater(profile["analyzed_chars"], 0)

    def test_document_intelligence_participates_in_rag(self) -> None:
        data = (
            "# Регламент закупок\n\n"
            "## Срок согласования\n\n"
            "Согласование заявки занимает пять рабочих дней.\n"
        ).encode("utf-8")
        document, structured = self._store("procurement.md", data)
        build_local_document_intelligence(
            self.project_id,
            int(document["id"]),
            structured,
        )
        init_rag()

        result = retrieve(
            self.project_id,
            "срок согласования заявки",
            limit=8,
            include_memory=False,
            include_knowledge=False,
        )
        self.assertTrue(
            any(
                item.metadata
                and item.metadata.get("retrieval_kind") == "document_intelligence"
                for item in result.items
            )
        )

    def test_tool_registry_exposes_document_intelligence_tools(self) -> None:
        names = {item["name"] for item in list_tools()}
        self.assertIn("project_document_understanding", names)
        self.assertIn("project_document_outline", names)
        self.assertIn("project_document_deep_search", names)

    def test_running_background_task_is_requeued_after_restart(self) -> None:
        task = create_task(
            self.project_id,
            "document_intelligence",
            {"document_id": 123},
        )
        claimed = claim_next_task()
        self.assertEqual(int(claimed["id"]), int(task["id"]))

        recovery = mark_interrupted_runtime_for_recovery()
        self.assertGreaterEqual(recovery["tasks_requeued"], 1)

        claimed_again = claim_next_task()
        self.assertEqual(int(claimed_again["id"]), int(task["id"]))


if __name__ == "__main__":
    unittest.main()
