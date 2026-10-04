from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from miyori.chat_intelligence import plan_chat_query,enhance_context_route
from miyori.chat_metrics import init_chat_metrics_db,store_model_usage,model_usage_summary
from miyori.config import settings
from miyori.db import init_db,create_project,ensure_conversation,add_message


class ChatQueryPlanTests(unittest.TestCase):
    def test_simple_chat_stays_fast(self):
        plan=plan_chat_query("Привет",[{"role":"user","content":"Привет"}])
        self.assertEqual(plan.depth,"fast")
        self.assertFalse(plan.is_followup)
        route=enhance_context_route("Привет",plan)
        self.assertFalse(route.use_documents)
        self.assertFalse(route.use_tools)

    def test_followup_uses_previous_question_only_for_retrieval(self):
        history=[
            {"role":"user","content":"Создай файл и найди договор АО Север"},
            {"role":"assistant","content":"Результат"},
            {"role":"user","content":"А какая дата?"}
        ]
        plan=plan_chat_query("А какая дата?",history)
        self.assertTrue(plan.is_followup)
        self.assertIn("договор АО Север",plan.retrieval_query)
        route=enhance_context_route("А какая дата?",plan)
        self.assertTrue(route.use_documents)
        self.assertFalse(route.use_tools,
                         "Previous write instructions must never authorize a new tool.")

    def test_followup_cannot_override_explicit_opt_out(self):
        history=[
            {"role":"user","content":"Найди контракт в документах"},
            {"role":"user","content":"А без документов какой ответ?"}
        ]
        plan=plan_chat_query("А без документов какой ответ?",history)
        route=enhance_context_route("А без документов какой ответ?",plan)
        self.assertFalse(route.use_documents)

    def test_deep_depth_for_multi_document_comparison(self):
        history=[{"role":"user","content":"Сравни договор и счет"}]
        plan=plan_chat_query("Сравни договор и счет",history,2)
        self.assertEqual(plan.depth,"deep")
        route=enhance_context_route("Сравни договор и счет",plan)
        self.assertGreaterEqual(route.max_rag_items,12)

    def test_read_only_disables_current_write_tools(self):
        plan=plan_chat_query("Создай файл",[{"role":"user","content":"Создай файл"}])
        route=enhance_context_route("Создай файл",plan,forced_read_only=True)
        self.assertFalse(route.use_tools)


class ActualUsageMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_dir=settings.data_dir
        self.old_db=settings.database_path
        root=Path(self.tmp.name)
        object.__setattr__(settings,"data_dir",root/"data")
        object.__setattr__(settings,"database_path",root/"data"/"usage.sqlite3")
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        init_db()
        init_chat_metrics_db()
        self.a=int(create_project("A")["id"])
        self.b=int(create_project("B")["id"])
    def tearDown(self):
        object.__setattr__(settings,"data_dir",self.old_dir)
        object.__setattr__(settings,"database_path",self.old_db)
        self.tmp.cleanup()

    def test_usage_is_project_scoped_and_unpriced_by_default(self):
        cid=ensure_conversation(None,self.a)
        mid=add_message(cid,"assistant","ok")
        store_model_usage(self.a,mid,{
            "model":"model-A","prompt_tokens":120,
            "completion_tokens":30,"total_tokens":150,
            "latency_ms":1000,"estimated_cost_rub":None,
        })
        store_model_usage(self.a,mid,{"model":"changed","total_tokens":10000})
        values=model_usage_summary(self.a)
        self.assertEqual(values["requests"],1)
        self.assertEqual(values["total_tokens"],150)
        self.assertIsNone(values["estimated_cost_rub"])
        self.assertFalse(values["billing_verified"])
        self.assertEqual(model_usage_summary(self.b)["requests"],0)


if __name__=="__main__":
    unittest.main()
