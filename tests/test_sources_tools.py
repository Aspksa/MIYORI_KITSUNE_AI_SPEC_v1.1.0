from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_document,
    create_project,
    decide_permission_request,
    init_db,
    list_permission_requests,
)
from miyori.documents import project_drive_dir, save_original, sha256_bytes
from miyori.sources import build_answer_sources
from miyori.tools import execute_approved_request, execute_tool


class SourcesAndToolSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("Tools A")
        self.other = create_project("Tools B")

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _document(self, project_id: int, name: str, content: str) -> dict:
        data = content.encode("utf-8")
        digest = sha256_bytes(data)
        stored = save_original(project_id, name, data, digest)
        return add_document(
            project_id,
            name,
            stored,
            "text/plain",
            digest,
            len(data),
            [content],
        )

    def test_answer_sources_deduplicate_document(self) -> None:
        rag = {
            "items": [
                {
                    "source_type": "document",
                    "title": "contract.pdf",
                    "locator": "document:5/chunk:1",
                    "metadata": {"document_id": 5, "chunk_index": 1},
                },
                {
                    "source_type": "document",
                    "title": "contract.pdf",
                    "locator": "document:5/chunk:2",
                    "metadata": {"document_id": 5, "chunk_index": 2},
                },
            ]
        }
        sources = build_answer_sources(9, rag, [])
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["chunk_indexes"], [1, 2])
        self.assertEqual(
            sources[0]["download_url"],
            "/api/projects/9/documents/5/download",
        )

    def test_exhaustive_question_source_keeps_document_and_locator(self) -> None:
        sources = build_answer_sources(
            self.project["id"],
            {"items": []},
            [
                {
                    "tool": "project_document_question_status",
                    "result": {
                        "document": {
                            "id": 17,
                            "filename": "book.pdf",
                        },
                        "question": {
                            "answer": {
                                "evidence": [
                                    {
                                        "text": "Найденный факт.",
                                        "locator": "pdf:page:42:lines:3-8",
                                    }
                                ]
                            }
                        },
                    },
                }
            ],
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["document_id"], 17)
        self.assertEqual(
            sources[0]["locator"],
            "pdf:page:42:lines:3-8",
        )

    def test_invalid_write_arguments_do_not_create_permission_request(self) -> None:
        with self.assertRaises(ValueError):
            execute_tool(
                "drive_folder_create",
                self.project["id"],
                {"unexpected": "value"},
                reason="Некорректный planner payload.",
            )
        self.assertEqual(list_permission_requests(self.project["id"]), [])

    def test_write_tool_never_executes_without_approval(self) -> None:
        result = execute_tool(
            "drive_folder_create",
            self.project["id"],
            {"name": "Договоры 2027", "parent_id": None},
            reason="Пользователь просит создать папку.",
        )
        self.assertEqual(result["status"], "approval_required")
        self.assertFalse(
            (project_drive_dir(self.project["id"]) / "Файлы" / "Договоры 2027").exists()
        )

        request_id = int(result["permission_request"]["id"])
        decided = decide_permission_request(self.project["id"], request_id, True)
        self.assertEqual(decided["status"], "approved")
        execution = execute_approved_request(self.project["id"], request_id)
        self.assertEqual(execution["status"], "executed")
        self.assertTrue(
            (project_drive_dir(self.project["id"]) / "Файлы" / "Договоры 2027").is_dir()
        )

    def test_document_read_cannot_cross_project_boundary(self) -> None:
        document = self._document(
            self.other["id"],
            "secret.txt",
            "Документ другого проекта.",
        )
        with self.assertRaises(ValueError):
            execute_tool(
                "project_document_read",
                self.project["id"],
                {"document_id": document["id"], "start": 0, "limit": 5},
            )


if __name__ == "__main__":
    unittest.main()
