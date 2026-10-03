from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import add_memory_fact, connect, create_project, init_db, utc_now
from miyori.epistemic import add_evidence, create_claim, create_source, init_epistemic_db
from miyori.rag import init_rag, rag_status, retrieve


class RAGCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_database_path = settings.database_path
        self._tmp = tempfile.TemporaryDirectory()
        object.__setattr__(settings, "database_path", Path(self._tmp.name) / "rag.sqlite3")
        init_db()
        init_epistemic_db()
        self.project = create_project("RAG Test")

        with connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents(project_id, filename, stored_path, mime_type, sha256, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.project["id"], "architecture.md", "test/architecture.md",
                    "text/markdown", "a" * 64, 200, utc_now(),
                ),
            )
            doc_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO document_chunks(document_id, chunk_index, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    doc_id, 0,
                    "Архитектура Miyori использует локальный RAG и SQLite для поиска контекста.",
                    utc_now(),
                ),
            )

        add_memory_fact(
            self.project["id"],
            "Пользователь предпочитает компактный интерфейс.",
            status="verified",
            source_kind="user_message",
        )
        add_memory_fact(
            self.project["id"],
            "Пользователь любит совершенно нерелевантный чай.",
            status="verified",
            source_kind="user_message",
        )

        claim = create_claim(self.project["id"], "Проект использует SQLite.", claim_type="fact")
        a = create_source(
            self.project["id"], "external",
            title="A", quality=0.9, independent_group="a",
        )
        b = create_source(
            self.project["id"], "external",
            title="B", quality=0.9, independent_group="b",
        )
        add_evidence(self.project["id"], claim["id"], a["id"], "supports")
        add_evidence(self.project["id"], claim["id"], b["id"], "supports")

        init_rag()

    def tearDown(self) -> None:
        object.__setattr__(settings, "database_path", self._old_database_path)
        self._tmp.cleanup()

    def test_document_retrieval(self) -> None:
        result = retrieve(self.project["id"], "Как устроен RAG и SQLite?", limit=8)
        self.assertTrue(any(item.source_type == "document" for item in result.items))
        self.assertIn(result.retrieval_mode, {"hybrid_fts_rrf", "hybrid_lexical_rrf"})

    def test_verified_memory_retrieval_is_relevant(self) -> None:
        result = retrieve(self.project["id"], "Какой интерфейс предпочитает пользователь?", limit=8)
        texts = [item.content for item in result.items if item.source_type == "memory"]
        self.assertTrue(any("компактный интерфейс" in text for text in texts))
        self.assertFalse(any("чай" in text for text in texts))

    def test_verified_epistemic_knowledge_retrieval(self) -> None:
        result = retrieve(self.project["id"], "Какую базу использует проект SQLite?", limit=8)
        knowledge = [item for item in result.items if item.source_type == "knowledge"]
        self.assertTrue(any("SQLite" in item.content for item in knowledge))
        self.assertTrue(any(item.metadata.get("status") == "verified" for item in knowledge))

    def test_context_budget(self) -> None:
        result = retrieve(
            self.project["id"],
            "RAG SQLite архитектура",
            limit=8,
            max_context_chars=120,
        )
        self.assertLessEqual(result.total_chars, 120)
        self.assertEqual(result.total_chars, sum(len(item.content) for item in result.items))

    def test_rag_status_is_explicit(self) -> None:
        status = rag_status()
        self.assertIn("fts5", status)
        self.assertIn("indexed_chunks", status)
        if status["fts5"]:
            self.assertEqual(status["indexed_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
