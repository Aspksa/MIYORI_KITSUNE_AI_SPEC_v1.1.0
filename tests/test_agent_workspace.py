from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from miyori import agent_workspace as aw
from miyori.config import settings
from miyori.agent import run_agent
from miyori.context_router import route_context
from miyori.db import create_project, get_agent_workflow, init_db, list_permission_requests


class AgentWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        aw.init_agent_workspace_db()
        self.project = create_project("Agent Workspace", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_default_workspace_is_valid_dag_with_budgets(self) -> None:
        workspace = aw.create_agent_workspace(
            self.project_id,
            "Проверить договор и подготовить решение.",
        )
        self.assertEqual(workspace["status"], "planned")
        self.assertEqual(workspace["max_parallel"], 2)
        self.assertEqual(len(workspace["nodes"]), 3)
        by_key = {item["node_key"]: item for item in workspace["nodes"]}
        self.assertEqual(by_key["research"]["status"], "ready")
        self.assertEqual(by_key["risk_review"]["status"], "ready")
        self.assertEqual(by_key["coordinator"]["status"], "blocked")
        self.assertEqual(
            set(by_key["coordinator"]["dependencies"]),
            {"research", "risk_review"},
        )
        self.assertLessEqual(workspace["total_step_budget"], aw.MAX_WORKSPACE_STEPS)

    def test_cycles_and_excessive_budget_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aw.create_agent_workspace(
                self.project_id,
                "Cycle",
                [
                    {
                        "key": "a",
                        "role": "A",
                        "title": "A",
                        "instruction": "A",
                        "depends_on": ["b"],
                        "step_budget": 1,
                    },
                    {
                        "key": "b",
                        "role": "B",
                        "title": "B",
                        "instruction": "B",
                        "depends_on": ["a"],
                        "step_budget": 1,
                    },
                ],
            )

        with self.assertRaises(ValueError):
            aw.create_agent_workspace(
                self.project_id,
                "Budget",
                [
                    {
                        "key": f"n{i}",
                        "role": "Agent",
                        "title": f"Node {i}",
                        "instruction": "Work",
                        "depends_on": [],
                        "step_budget": 5,
                    }
                    for i in range(5)
                ],
            )

    def test_cycle_runs_independent_nodes_in_parallel_then_dependency(self) -> None:
        workspace = aw.create_agent_workspace(
            self.project_id,
            "Parallel test",
            max_parallel=2,
        )
        starts: dict[str, float] = {}
        finishes: dict[str, float] = {}
        lock = threading.Lock()

        def fake_run(project_id: int, workspace_id: int, node: dict) -> dict:
            with lock:
                starts[node["node_key"]] = time.monotonic()
            if node["node_key"] in {"research", "risk_review"}:
                time.sleep(0.06)
            current = aw.get_agent_workspace(project_id, workspace_id)
            if node["node_key"] == "coordinator":
                by_key = {item["node_key"]: item for item in current["nodes"]}
                self.assertEqual(by_key["research"]["status"], "completed")
                self.assertEqual(by_key["risk_review"]["status"], "completed")
            aw._update_node(
                int(node["id"]),
                status="completed",
                result={"node_key": node["node_key"]},
                mark_started=True,
                mark_finished=True,
            )
            with lock:
                finishes[node["node_key"]] = time.monotonic()
            return {"node_id": node["id"], "status": "completed"}

        with patch.object(aw, "_run_node", side_effect=fake_run):
            result = aw.run_agent_workspace_cycle(
                self.project_id,
                {"workspace_id": workspace["id"]},
            )

        final = result["workspace"]
        self.assertEqual(final["status"], "completed")
        self.assertEqual(len(result["batches"]), 2)
        first = {item["node_id"] for item in result["batches"][0]["nodes"]}
        first_expected = {
            item["id"]
            for item in workspace["nodes"]
            if item["node_key"] in {"research", "risk_review"}
        }
        self.assertEqual(first, first_expected)
        self.assertLess(
            abs(starts["research"] - starts["risk_review"]),
            0.05,
        )
        self.assertGreaterEqual(
            starts["coordinator"],
            max(finishes["research"], finishes["risk_review"]),
        )

    def test_waiting_permission_pauses_workspace_without_running_dependency(self) -> None:
        workspace = aw.create_agent_workspace(self.project_id, "Permission test")

        def fake_run(project_id: int, workspace_id: int, node: dict) -> dict:
            if node["node_key"] == "research":
                aw._update_node(
                    int(node["id"]),
                    status="waiting_permission",
                    result={"permission": "pending"},
                    mark_started=True,
                )
                return {"node_id": node["id"], "status": "waiting_permission"}
            aw._update_node(
                int(node["id"]),
                status="completed",
                result={"ok": True},
                mark_started=True,
                mark_finished=True,
            )
            return {"node_id": node["id"], "status": "completed"}

        with patch.object(aw, "_run_node", side_effect=fake_run):
            result = aw.run_agent_workspace_cycle(
                self.project_id,
                {"workspace_id": workspace["id"]},
            )

        final = result["workspace"]
        self.assertEqual(final["status"], "waiting_permission")
        by_key = {item["node_key"]: item for item in final["nodes"]}
        self.assertEqual(by_key["coordinator"]["status"], "blocked")

    def test_cancel_marks_unstarted_nodes_cancelled(self) -> None:
        workspace = aw.create_agent_workspace(self.project_id, "Cancel test")
        final = aw.cancel_agent_workspace(self.project_id, int(workspace["id"]))
        self.assertEqual(final["status"], "cancelled")
        self.assertTrue(
            all(item["status"] == "cancelled" for item in final["nodes"])
        )


    def test_read_only_capability_is_hard_enforced_in_workflow(self) -> None:
        result = __import__("asyncio").run(
            run_agent(
                self.project_id,
                None,
                'Создай папку «forbidden»',
                route_context('Создай папку «forbidden»'),
                [],
                request_key="workspace:read-only:test",
                max_steps=2,
                tool_permissions=("read",),
            )
        )
        workflow = get_agent_workflow(result.workflow_id, self.project_id)
        self.assertEqual(workflow["route"]["_tool_permissions"], ["read"])
        self.assertEqual(result.workflow_status, "completed")
        self.assertEqual(list_permission_requests(self.project_id), [])

    def test_enqueue_is_idempotent_while_task_is_active(self) -> None:
        workspace = aw.create_agent_workspace(self.project_id, "Queue once")
        first = aw.enqueue_agent_workspace(self.project_id, int(workspace["id"]))
        second = aw.enqueue_agent_workspace(self.project_id, int(workspace["id"]))
        self.assertEqual(first["id"], second["id"])

    def test_cancel_does_not_lie_when_child_recovery_blocks_cancel(self) -> None:
        workspace = aw.create_agent_workspace(self.project_id, "Recovery cancel")
        node = workspace["nodes"][0]
        aw._update_node(
            int(node["id"]),
            status="running",
            workflow_id=777,
            mark_started=True,
        )
        with patch.object(
            aw,
            "cancel_agent_workflow",
            side_effect=RuntimeError("recovery first"),
        ):
            final = aw.cancel_agent_workspace(self.project_id, int(workspace["id"]))

        self.assertEqual(final["status"], "recovery")
        by_id = {int(item["id"]): item for item in final["nodes"]}
        self.assertEqual(by_id[int(node["id"])]["status"], "recovery")
        self.assertTrue(
            all(
                item["status"] == "cancelled"
                for item in final["nodes"]
                if int(item["id"]) != int(node["id"])
            )
        )

if __name__ == "__main__":
    unittest.main()
