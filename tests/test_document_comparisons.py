from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from miyori.config import settings
from miyori.db import create_project,init_db,add_document,ensure_conversation
from miyori.documents import extract_structured_document,save_original,sha256_bytes,chunk_text
from miyori.document_intelligence import init_document_intelligence_db,build_local_document_intelligence
from miyori.document_questions import init_document_questions_db
from miyori.document_comparisons import (
    init_document_comparisons_db,enqueue_document_comparison,get_document_comparison,
)


class DocumentComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_path=settings.database_path
        root=Path(self.tmp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"db.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        init_document_intelligence_db()
        init_document_questions_db()
        init_document_comparisons_db()
        self.project=int(create_project("Comparisons")["id"])
        self.other=int(create_project("Other")["id"])
        self.cid=ensure_conversation(None,self.project)
        self.docs=[self._make_document("agreement.md","Сумма 100 рублей. Дата 01.03.2026."),
                   self._make_document("invoice.md","Сумма 110 рублей. Дата 02.03.2026.")]

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_path)
        self.tmp.cleanup()

    def _make_document(self,name,text):
        data=("# "+name+"\n\n"+text*12).encode()
        structured=extract_structured_document(name,data)
        sha=sha256_bytes(data)
        path=save_original(self.project,name,data,sha)
        doc=add_document(
            self.project,name,path,"text/markdown",sha,len(data),
            chunk_text(structured.text),
        )
        build_local_document_intelligence(
            self.project,int(doc["id"]),structured
        )
        return int(doc["id"])

    def test_persist_and_idempotently_resume_existing_checks(self):
        first=enqueue_document_comparison(
            self.project,self.docs,"Сравни даты и суммы",conversation_id=self.cid
        )
        self.assertEqual(first["status"],"working")
        self.assertEqual(len(first["documents"]),2)
        self.assertFalse(first["full_originals_verified"])
        second=enqueue_document_comparison(
            self.project,list(reversed(self.docs)),
            "Сравни даты и суммы",conversation_id=self.cid,
        )
        self.assertEqual(first["id"],second["id"])
        for item in second["documents"]:
            self.assertTrue(item["task_id"])

    def test_reject_cross_project_or_duplicate_document(self):
        with self.assertRaises(ValueError):
            enqueue_document_comparison(self.other,self.docs,"Сравни")
        with self.assertRaises(ValueError):
            enqueue_document_comparison(self.project,[self.docs[0]]*2,"Сравни")
        with self.assertRaises(ValueError):
            enqueue_document_comparison(
                self.project,self.docs,"Сравни",
                conversation_id=ensure_conversation(None,self.other)
            )
        with self.assertRaises(LookupError):
            get_document_comparison(self.other,999)

    def test_no_false_coverage_or_verified_inference(self):
        entry=enqueue_document_comparison(self.project,self.docs,"Проверь")
        other=get_document_comparison(self.project,entry["id"])
        self.assertFalse(other["finished"])
        self.assertFalse(other["full_originals_verified"])
        self.assertTrue(all(item.get("coverage_ratio",0) <=1 for item in other["documents"]))


if __name__=="__main__":
    unittest.main()
