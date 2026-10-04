from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_document,
    add_memory_fact,
    connect,
    create_project,
    init_db,
    utc_now,
)
from miyori.document_intelligence import init_document_intelligence_db
from miyori.document_questions import init_document_questions_db
from miyori.epistemic import (
    add_evidence,
    create_claim,
    create_source,
    init_epistemic_db,
)
from miyori.nexus_knowledge import (
    NEXUS_KNOWLEDGE_SCHEMA_VERSION,
    build_nexus_knowledge_center,
)


class NexusKnowledgeContractTests(unittest.TestCase):
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
        init_document_questions_db()
        init_epistemic_db()
        self.project = create_project("NEXUS Knowledge", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def _add_document_profile(
        self,
        filename: str = "contract-alpha.txt",
        *,
        extraction_coverage: float = 1.0,
        coverage: float = 1.0,
        status: str = "complete",
        extraction_status: str = "complete",
    ) -> dict:
        document = add_document(
            self.project_id,
            filename,
            f"drive/{filename}",
            "text/plain",
            "a" * 64,
            128,
            ["Alpha contract text", "Second section"],
        )
        now = utc_now()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO document_intelligence(
                    document_id, project_id, status, parser_version,
                    source_sha256, title, document_kind, language,
                    char_count, word_count, page_count, section_count,
                    table_count, node_count, analyzed_chars, coverage_ratio,
                    extraction_status, extraction_coverage,
                    extraction_warnings_json, extraction_details_json,
                    summary_short, summary_long, outline_json,
                    keywords_json, analysis_json, analysis_model,
                    last_error, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, 'test-parser', ?, ?, 'text', 'ru',
                    32, 4, 1, 2, 0, 2, 32, ?,
                    ?, ?, ?, '{}',
                    'Alpha summary', 'Alpha long summary', '[]',
                    '["alpha"]', '{}', 'test-model',
                    NULL, ?, ?
                )
                """,
                (
                    int(document["id"]),
                    self.project_id,
                    status,
                    document["sha256"],
                    filename,
                    coverage,
                    extraction_status,
                    extraction_coverage,
                    '["Неполное извлечение"]' if extraction_coverage < 1 else "[]",
                    now,
                    now,
                ),
            )
        return document

    def test_contract_keeps_memory_documents_and_claims_distinct(self) -> None:
        memory = add_memory_fact(
            self.project_id,
            "Alpha process uses signed contracts.",
            status="verified",
            memory_scope="project",
            memory_kind="process",
            source_kind="user_message",
            confidence=1.0,
            verification_method="direct_user",
        )
        document = self._add_document_profile()

        source = create_source(
            self.project_id,
            "document",
            source_key=f"document:{document['id']}",
            title=document["filename"],
            locator=f"document:{document['id']}:text:1-2",
            quality=0.9,
            independent_group=f"document:{document['id']}",
        )
        claim = create_claim(
            self.project_id,
            "Alpha contract contains a signed approval clause.",
            claim_type="fact",
        )
        add_evidence(
            self.project_id,
            int(claim["id"]),
            int(source["id"]),
            "supports",
            excerpt="Signed approval clause.",
            weight=1.0,
        )

        center = build_nexus_knowledge_center(self.project_id)
        self.assertEqual(center["schema_version"], NEXUS_KNOWLEDGE_SCHEMA_VERSION)
        self.assertTrue(center["semantics"]["sections_are_distinct"])
        self.assertEqual(len(center["memory"]), 1)
        self.assertEqual(len(center["documents"]), 1)
        self.assertEqual(len(center["claims"]), 1)
        self.assertEqual(center["memory"][0]["id"], int(memory["id"]))
        self.assertEqual(center["documents"][0]["id"], int(document["id"]))
        self.assertEqual(center["claims"][0]["id"], int(claim["id"]))
        self.assertEqual(
            center["claims"][0]["evidence_preview"][0]["source"]["type"],
            "document",
        )

    def test_user_memory_is_visible_across_projects_but_project_memory_is_not(self) -> None:
        other = create_project("Other Knowledge", kind="work")
        add_memory_fact(
            int(other["id"]),
            "Global preferred report format is PDF.",
            status="verified",
            memory_scope="user",
            memory_kind="preference",
        )
        add_memory_fact(
            int(other["id"]),
            "Other project internal code is OMEGA.",
            status="verified",
            memory_scope="project",
            memory_kind="fact",
        )

        center = build_nexus_knowledge_center(self.project_id)
        statements = {item["statement"] for item in center["memory"]}
        self.assertIn("Global preferred report format is PDF.", statements)
        self.assertNotIn("Other project internal code is OMEGA.", statements)
        global_item = next(
            item
            for item in center["memory"]
            if item["statement"] == "Global preferred report format is PDF."
        )
        self.assertEqual(global_item["actions"]["project_id"], int(other["id"]))

    def test_query_returns_grouped_results_without_blending_types(self) -> None:
        add_memory_fact(
            self.project_id,
            "Alpha preference.",
            status="verified",
            memory_scope="project",
            memory_kind="preference",
        )
        self._add_document_profile(filename="beta-document.txt")
        claim = create_claim(
            self.project_id,
            "Gamma statement.",
            claim_type="fact",
        )

        center = build_nexus_knowledge_center(self.project_id, query="Gamma")
        self.assertEqual(center["results"]["memory"], 0)
        self.assertEqual(center["results"]["documents"], 0)
        self.assertEqual(center["results"]["claims"], 1)
        self.assertEqual(center["claims"][0]["id"], int(claim["id"]))

    def test_attention_comes_from_real_conflicts_and_document_limits(self) -> None:
        add_memory_fact(
            self.project_id,
            "Budget limit is 100.",
            status="disputed",
            memory_scope="project",
            memory_kind="constraint",
        )
        self._add_document_profile(
            extraction_coverage=0.5,
            coverage=0.4,
            status="partial",
            extraction_status="partial",
        )
        claim = create_claim(
            self.project_id,
            "Delivery date is 10 October.",
            claim_type="fact",
            status="disputed",
            confidence=0.5,
        )

        center = build_nexus_knowledge_center(self.project_id)
        attention = center["counts"]["attention"]
        self.assertGreaterEqual(attention["memory_disputed"], 1)
        self.assertGreaterEqual(attention["documents_limited"], 1)
        self.assertGreaterEqual(attention["claim_disputed"], 1)
        self.assertGreater(attention["total"], 0)
        self.assertEqual(center["claims"][0]["id"], int(claim["id"]))


if __name__ == "__main__":
    unittest.main()
