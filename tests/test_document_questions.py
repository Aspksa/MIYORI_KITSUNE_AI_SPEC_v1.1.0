from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from miyori.config import settings
from miyori.db import (
    add_document,
    create_project,
    init_db,
)
from miyori.document_intelligence import (
    build_document_windows,
    build_local_document_intelligence,
    init_document_intelligence_db,
)
from miyori.document_questions import (
    enqueue_exhaustive_document_question,
    get_document_question,
    init_document_questions_db,
    list_document_question_windows,
    run_exhaustive_document_question,
)
from miyori.documents import (
    chunk_text,
    extract_structured_document,
    save_original,
    sha256_bytes,
)


class ExhaustiveDocumentQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(
            settings,
            "database_path",
            root / "data" / "miyori.sqlite3",
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_document_questions_db()
        self.project = create_project("Exhaustive Q&A", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _store_long_document(self) -> dict:
        chapters = []
        for index in range(1, 13):
            marker = (
                " В этой главе действует специальное условие Альфа."
                if index in {3, 9}
                else ""
            )
            body = (
                f"Глава {index}. Контрольный материал {index}. "
                + ("Подробный текст для последовательной проверки. " * 150)
                + marker
            )
            chapters.append(f"## Глава {index}\n\n{body}")
        data = (
            "# Полная книга\n\n"
            + "\n\n".join(chapters)
        ).encode("utf-8")

        structured = extract_structured_document("full-book.md", data)
        digest = sha256_bytes(data)
        stored = save_original(
            self.project_id,
            "full-book.md",
            data,
            digest,
        )
        document = add_document(
            self.project_id,
            "full-book.md",
            stored,
            "text/markdown",
            digest,
            len(data),
            chunk_text(structured.text),
        )
        build_local_document_intelligence(
            self.project_id,
            int(document["id"]),
            structured,
        )
        return document

    def test_question_scans_every_window_and_returns_full_coverage(self) -> None:
        document = self._store_long_document()
        _, windows = build_document_windows(
            self.project_id,
            int(document["id"]),
        )
        self.assertGreater(len(windows), 2)

        async def fake_window(title, question, index, total, content):
            relevant = "условие Альфа" in content
            locator = content.split("]", 1)[0].lstrip("[")
            return {
                "relevant": relevant,
                "answer_fragment": (
                    f"Условие найдено в окне {index}" if relevant else ""
                ),
                "evidence": (
                    [{"text": "Специальное условие Альфа.", "locator": locator}]
                    if relevant else []
                ),
                "caveats": [],
            }

        async def fake_synthesis(title, question, results, coverage_ratio):
            evidence = []
            for item in results:
                evidence.extend(item.get("evidence") or [])
            return {
                "answer": "Условие Альфа встречается в двух частях документа.",
                "evidence": evidence,
                "caveats": [],
                "not_found": False,
                "confidence": "high",
            }

        queued = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "Где встречается условие Альфа?",
        )
        question_id = int(queued["id"])

        window_mock = AsyncMock(side_effect=fake_window)
        synth_mock = AsyncMock(side_effect=fake_synthesis)
        with patch(
            "miyori.document_questions.analyze_document_question_window",
            window_mock,
        ), patch(
            "miyori.document_questions.synthesize_exhaustive_document_answer",
            synth_mock,
        ):
            result = asyncio.run(
                run_exhaustive_document_question(
                    self.project_id,
                    question_id,
                )
            )

        self.assertEqual(window_mock.await_count, len(windows))
        self.assertEqual(result["status"], "complete")
        self.assertGreaterEqual(result["coverage_ratio"], 0.995)
        self.assertEqual(result["answer"]["windows_scanned"], len(windows))
        self.assertGreaterEqual(result["answer"]["windows_relevant"], 2)
        self.assertTrue(result["answer"]["evidence"])
        self.assertTrue(
            all(item.get("locator") for item in result["answer"]["evidence"])
        )

        saved_windows = list_document_question_windows(
            self.project_id,
            int(document["id"]),
            question_id,
        )
        self.assertEqual(len(saved_windows), len(windows))
        self.assertTrue(
            all(item["source_fingerprint"] for item in saved_windows)
        )

    def test_retry_after_failure_reuses_completed_windows(self) -> None:
        document = self._store_long_document()
        _, windows = build_document_windows(
            self.project_id,
            int(document["id"]),
        )
        queued = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "Проверь весь документ на контрольные условия.",
            force=True,
        )
        question_id = int(queued["id"])

        calls = {"count": 0}

        async def flaky_window(title, question, index, total, content):
            calls["count"] += 1
            if calls["count"] == 3:
                raise RuntimeError("simulated provider failure")
            return {
                "relevant": False,
                "answer_fragment": "",
                "evidence": [],
                "caveats": [],
            }

        with patch(
            "miyori.document_questions.analyze_document_question_window",
            AsyncMock(side_effect=flaky_window),
        ):
            with self.assertRaises(RuntimeError):
                asyncio.run(
                    run_exhaustive_document_question(
                        self.project_id,
                        question_id,
                    )
                )

        partial = get_document_question(
            self.project_id,
            int(document["id"]),
            question_id,
        )
        self.assertEqual(partial["status"], "partial")
        saved_before = list_document_question_windows(
            self.project_id,
            int(document["id"]),
            question_id,
        )
        self.assertEqual(len(saved_before), 2)

        retried = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "Проверь весь документ на контрольные условия.",
        )
        self.assertTrue(retried["existing"])
        self.assertTrue(retried["retrying"])
        self.assertEqual(int(retried["id"]), question_id)
        self.assertEqual(retried["status"], "queued")

        async def good_window(title, question, index, total, content):
            return {
                "relevant": False,
                "answer_fragment": "",
                "evidence": [],
                "caveats": [],
            }

        async def synthesis(title, question, results, coverage_ratio):
            return {
                "answer": "Проверка завершена.",
                "evidence": [],
                "caveats": [],
                "not_found": True,
                "confidence": "high",
            }

        retry_mock = AsyncMock(side_effect=good_window)
        with patch(
            "miyori.document_questions.analyze_document_question_window",
            retry_mock,
        ), patch(
            "miyori.document_questions.synthesize_exhaustive_document_answer",
            AsyncMock(side_effect=synthesis),
        ):
            completed = asyncio.run(
                run_exhaustive_document_question(
                    self.project_id,
                    question_id,
                )
            )

        self.assertEqual(
            retry_mock.await_count,
            len(windows) - len(saved_before),
        )
        self.assertEqual(completed["status"], "complete")
        self.assertGreaterEqual(completed["coverage_ratio"], 0.995)

    def test_same_question_reuses_completed_run(self) -> None:
        document = self._store_long_document()
        first = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "Есть ли условие Альфа?",
        )
        question_id = int(first["id"])

        async def no_match(title, question, index, total, content):
            return {
                "relevant": False,
                "answer_fragment": "",
                "evidence": [],
                "caveats": [],
            }

        async def synthesis(title, question, results, coverage_ratio):
            return {
                "answer": "Проверено.",
                "evidence": [],
                "caveats": [],
                "not_found": True,
                "confidence": "high",
            }

        with patch(
            "miyori.document_questions.analyze_document_question_window",
            AsyncMock(side_effect=no_match),
        ), patch(
            "miyori.document_questions.synthesize_exhaustive_document_answer",
            AsyncMock(side_effect=synthesis),
        ):
            asyncio.run(
                run_exhaustive_document_question(
                    self.project_id,
                    question_id,
                )
            )

        second = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "  Есть ли условие Альфа?  ",
        )
        self.assertTrue(second["existing"])
        self.assertEqual(int(second["id"]), question_id)
        self.assertEqual(second["status"], "complete")

    def test_question_is_project_isolated(self) -> None:
        document = self._store_long_document()
        queued = enqueue_exhaustive_document_question(
            self.project_id,
            int(document["id"]),
            "Проверить документ.",
        )
        other = create_project("Other project", kind="work")
        self.assertIsNone(
            get_document_question(
                int(other["id"]),
                int(document["id"]),
                int(queued["id"]),
            )
        )


if __name__ == "__main__":
    unittest.main()
