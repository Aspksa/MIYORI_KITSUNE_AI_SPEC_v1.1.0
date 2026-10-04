from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import init_db,create_project,add_document
from miyori.documents import (
    save_original,sha256_bytes,chunk_text,extract_structured_document,
)
from miyori.document_intelligence import (
    init_document_intelligence_db,build_local_document_intelligence,
)
from miyori.screen_context import (
    normalize_screen_context,resolve_screen_document,
)


class ScreenContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_db=settings.database_path
        root=Path(self.tmp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"db.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        init_document_intelligence_db()
        self.project=int(create_project("Screen Work")["id"])
        self.other=int(create_project("Private")["id"])
        self.doc=self.add_doc(
            self.project,"selected.md",
            "Договор № ABC-2026. Дата подписания 15.09.2026."
        )

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_db)
        self.tmp.cleanup()

    def add_doc(self,project,name,text):
        content=("# "+name+"\n\n"+text).encode("utf-8")
        sha=sha256_bytes(content)
        path=save_original(project,name,content,sha)
        structured=extract_structured_document(name,content)
        doc=add_document(project,name,path,"text/markdown",sha,
                         len(content),chunk_text(structured.text))
        build_local_document_intelligence(project,int(doc["id"]),structured)
        return int(doc["id"])

    def test_document_ownership_and_enum_protection(self):
        ctx=normalize_screen_context(
            self.project,{"module":"documents","document_id":self.doc}
        )
        self.assertEqual(ctx["document_id"],self.doc)
        with self.assertRaises(ValueError):
            normalize_screen_context(
                self.other,{"module":"documents","document_id":self.doc}
            )
        with self.assertRaises(ValueError):
            normalize_screen_context(
                self.project,{"module":"actions","document_id":self.doc}
            )
        self.assertEqual(
            normalize_screen_context(self.project,
                                     {"module":"totally_other","document_id":self.doc}),
            {}
        )

    def test_explicit_reference_loads_attributed_text(self):
        ctx=normalize_screen_context(
            self.project,{"module":"documents","document_id":self.doc}
        )
        chunks,sources=resolve_screen_document(
            self.project,"Что здесь указано по договору?",ctx
        )
        self.assertTrue(chunks)
        self.assertIn("selected.md",chunks[0]["filename"])
        self.assertEqual(sources[0]["document_id"],self.doc)
        self.assertTrue(sources[0]["unverified"])

    def test_unrelated_chat_cannot_automatically_read_last_file(self):
        ctx=normalize_screen_context(
            self.project,{"module":"documents","document_id":self.doc}
        )
        snippets,sources=resolve_screen_document(
            self.project,"Привет, как настроение?",ctx
        )
        self.assertEqual(snippets,[])
        self.assertEqual(sources,[])

    def test_no_project_crossing_even_if_caller_forges_a_screen_hint(self):
        with self.assertRaises(ValueError):
            normalize_screen_context(
                self.other,{"module":"documents","document_id":self.doc}
            )
        chunks,sources=resolve_screen_document(
            self.other,"Прочитай этот документ",
            {"module":"documents","document_id":self.doc},
        )
        self.assertEqual(chunks,[])
        self.assertEqual(sources,[])


if __name__=="__main__":
    unittest.main()
