from __future__ import annotations
import unittest
from miyori.answer_check import check_numeric_support


class NumericAnswerCheckTests(unittest.TestCase):
    def test_numbers_from_same_context_match(self):
        answer="По договору Восток сумма 110 рублей."
        rag=[{"source_type":"document",
              "content":"По договору Восток сумма 110 рублей за работы."}]
        check=check_numeric_support(answer,rag_items=rag)
        self.assertEqual(check["claims_seen"],1)
        self.assertEqual(check["matching_source"],1)
        self.assertFalse(check["semantic_fact_verification"])

    def test_number_missing_from_source_is_flagged_not_asserted_false(self):
        check=check_numeric_support(
            "По договору Восток сумма 150 рублей.",
            rag_items=[{"source_type":"document",
                        "content":"По договору Восток сумма 110 рублей."}],
        )
        self.assertEqual(check["missing_source"],1)
        self.assertIn("не найдены",check["warnings"][0]["reason"])

    def test_same_number_in_unrelated_source_does_not_pass(self):
        check=check_numeric_support(
            "По договору Восток сумма 110 рублей.",
            rag_items=[{"source_type":"document",
                        "content":"Данные о машине: пробег 110 километров."}],
        )
        self.assertEqual(check["matching_source"],0)

    def test_no_sources_or_unverified_claims_cannot_be_fact_checked(self):
        answer="Стоимость по договору 110 рублей."
        check=check_numeric_support(answer,verified_claims=[
            {"statement":"Стоимость по договору 110 рублей.","status":"candidate"}
        ])
        self.assertEqual(check["status"],"not_applicable")
        self.assertFalse(check["semantic_fact_verification"])

    def test_date_and_amounts_not_conflated(self):
        check=check_numeric_support(
            "Оплата по договору до 01.03.2026. Сумма по договору 150 рублей.",
            document_fragments=[{
                "content":"Сумма по договору 150 рублей. Дата оплаты 02.03.2026."
            }]
        )
        self.assertGreaterEqual(check["claims_seen"],2)
        self.assertGreaterEqual(check["missing_source"],1)


if __name__=="__main__":
    unittest.main()
