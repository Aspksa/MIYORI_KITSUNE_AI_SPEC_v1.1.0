from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from miyori.config import settings
from miyori.db import add_document,create_project,init_db
from miyori.chat_document_review import compare_project_documents,MAX_CHUNKS_PER_FILE


class SourceBoundedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_db=settings.database_path
        root=Path(self.tmp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"test.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        self.a=int(create_project("Договоры А")["id"])
        self.b=int(create_project("Договоры Б")["id"])

    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_db)
        self.tmp.cleanup()

    def doc(self,project,name,chunks):
        return int(add_document(
            project,name,name,"text/plain",
            (name+str(project)).encode().hex()[:64],
            sum(len(x) for x in chunks),chunks,
        )["id"])

    def test_differences_have_real_document_and_chunk_provenance(self):
        first=self.doc(self.a,"Договор.txt",[
            "ИНН 1234567890. Цена 1 200,00 руб. НДС 20%. Дата 01.02.2026."
        ])
        second=self.doc(self.a,"Счёт.txt",[
            "ИНН 1234567890. Цена 1 450,00 ₽. НДС 10%. Дата 03.02.2026."
        ])
        result=compare_project_documents(self.a,[first,second])
        self.assertFalse(result["fact_verified"])
        self.assertFalse(result["original_fully_verified"])
        by_field={d["field"]:d for d in result["potential_differences"]}
        self.assertIn("НДС",by_field)
        self.assertIn("Денежные суммы",by_field)
        self.assertIn("Даты",by_field)
        self.assertNotIn("ИНН",by_field)
        for row in by_field["Денежные суммы"]["evidence"]:
            self.assertIn(row["document_id"],[first,second])
            self.assertEqual(row["values"][0]["chunk_index"],0)
            self.assertTrue(row["values"][0]["excerpt"])
        self.assertEqual(result["difference_count"],3)

    def test_project_boundary_and_duplicate_ids(self):
        first=self.doc(self.a,"A.txt",["НДС 20%"])
        other=self.doc(self.b,"B.txt",["НДС 10%"])
        with self.assertRaises(ValueError):
            compare_project_documents(self.a,[first,other])
        with self.assertRaises(ValueError):
            compare_project_documents(self.a,[first,first])

    def test_unreadable_scan_requires_ocr(self):
        first=self.doc(self.a,"empty.pdf",[])
        second=self.doc(self.a,"ok.txt",["Договор от 01.01.2026"])
        result=compare_project_documents(self.a,[first,second])
        self.assertTrue(result["documents"][0]["requires_ocr"])
        self.assertFalse(result["all_stored_text_scanned"])

    def test_chunk_scan_is_bounded_without_false_full_coverage(self):
        first=self.doc(self.a,"long.txt",[
            "Дата 01.01.2026" for _ in range(MAX_CHUNKS_PER_FILE+1)
        ])
        second=self.doc(self.a,"short.txt",["Дата 01.01.2026"])
        result=compare_project_documents(self.a,[first,second])
        long=result["documents"][0]
        self.assertEqual(long["text_chunks_total"],MAX_CHUNKS_PER_FILE+1)
        self.assertEqual(long["text_chunks_scanned"],MAX_CHUNKS_PER_FILE)
        self.assertFalse(long["stored_text_scanned"])
        self.assertFalse(result["all_stored_text_scanned"])


if __name__=="__main__":
    unittest.main()
