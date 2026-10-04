from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    init_db,create_project,add_document,mark_document_deleted,
)
from miyori.documents import (
    extract_structured_document,save_original,sha256_bytes,chunk_text,
)
from miyori.document_intelligence import (
    init_document_intelligence_db,build_local_document_intelligence,
)
from miyori.document_links import extract_identifiers,related_documents


class SourceBackedDocumentLinks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_path=settings.database_path
        root=Path(self.temp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"db.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        init_document_intelligence_db()
        self.project=int(create_project("Work")["id"])
        self.other=int(create_project("Foreign")["id"])
        self.contract=self.add_doc(
            self.project,"dogovor.md",
            "Договор № ABC-2026. Автомобиль А123ВС125. "
            "VIN XTA210990Y1234567. Сумма 150 рублей.",
        )
        self.invoice=self.add_doc(
            self.project,"invoice.md",
            "Счёт-оферта № INV-2026. Основание: договор № ABC-2026. "
            "А123ВС125 на ремонт. Всего 170 рублей.",
        )
        self.unrelated=self.add_doc(
            self.project,"other.md",
            "Иной договор № DEF-2026. Цена тоже 150 рублей.",
        )
        self.foreign=self.add_doc(
            self.other,"secret.md",
            "Договор № ABC-2026. Секрет контрагента!",
        )

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_path)
        self.temp.cleanup()

    def add_doc(self,project,name,text):
        blob=("# "+name+"\n\n"+text).encode("utf-8")
        structured=extract_structured_document(name,blob)
        sha=sha256_bytes(blob)
        location=save_original(project,name,blob,sha)
        record=add_document(project,name,location,"text/markdown",
                            sha,len(blob),chunk_text(structured.text))
        build_local_document_intelligence(project,int(record["id"]),structured)
        return int(record["id"])

    def test_extract_only_typed_strong_references(self):
        matches=extract_identifiers("Договор № ABC-2026; "
                                    "госномер А123ВС125; VIN XTA210990Y1234567")
        self.assertIn(("contract_number","ABC-2026"),matches)
        self.assertIn(("registration","А123ВС125"),matches)
        self.assertIn(("vin","XTA210990Y1234567"),matches)
        self.assertNotIn(("contract_number","150"),extract_identifiers(
            "Сумма: 150 рублей. Дата: 01.03.2026"))

    def test_links_have_both_source_locators_but_not_unrelated_amounts(self):
        result=related_documents(self.project,self.contract)
        self.assertFalse(result["verified_relationship"])
        ids={x["document_id"] for x in result["candidates"]}
        self.assertIn(self.invoice,ids)
        self.assertNotIn(self.unrelated,ids)
        self.assertNotIn(self.foreign,ids)
        related=next(x for x in result["candidates"]
                     if x["document_id"]==self.invoice)
        self.assertGreater(related["match_count"],0)
        for match in related["matches"]:
            self.assertTrue(match["source"]["locator"])
            self.assertTrue(match["target"]["locator"])

    def test_deleted_or_foreign_document_cannot_leak(self):
        with self.assertRaises(LookupError):
            related_documents(self.other,self.contract)
        with self.assertRaises(LookupError):
            related_documents(self.project,self.foreign)
        mark_document_deleted(self.project,self.invoice,"trash/path")
        result=related_documents(self.project,self.contract)
        ids={x["document_id"] for x in result["candidates"]}
        self.assertNotIn(self.invoice,ids)


if __name__=="__main__":
    unittest.main()
