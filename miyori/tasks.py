from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .system_settings import load_system_settings

from .db import (
    claim_next_task,
    finish_task,
    is_task_cancel_requested,
    record_task_event,
)

TaskHandler = Callable[[int, dict], dict]

_handlers: dict[str, TaskHandler] = {}
_worker_lock = threading.Lock()
_worker_running = False
_monitor_running = False


def register_task_handler(name: str, handler: TaskHandler) -> None:
    _handlers[name] = handler


def _run_worker() -> None:
    global _worker_running
    try:
        iterations = 0
        max_iterations = 20

        while iterations < max_iterations:
            task = claim_next_task()
            if not task:
                break

            task_id = int(task["id"])
            task_type = task["task_type"]
            project_id = int(task["project_id"])
            payload = task["payload"]

            if is_task_cancel_requested(task_id):
                finish_task(task_id, "cancelled", {"message": "Отменено до запуска."})
                iterations += 1
                continue

            handler = _handlers.get(task_type)
            if not handler:
                finish_task(task_id, "failed", {"error": "Нет обработчика задачи."})
                iterations += 1
                continue

            try:
                record_task_event(task_id, "started", f"Запуск {task_type}")
                result = handler(project_id, payload)
                if is_task_cancel_requested(task_id):
                    finish_task(task_id, "cancelled", {"message": "Отменено пользователем."})
                else:
                    finish_task(task_id, "completed", result)
            except Exception as exc:
                finish_task(task_id, "failed", {"error": str(exc)})

            iterations += 1
    finally:
        with _worker_lock:
            _worker_running = False


def wake_worker() -> None:
    global _worker_running
    with _worker_lock:
        if _worker_running:
            return
        _worker_running = True

    thread = threading.Thread(target=_run_worker, daemon=True, name="miyori-task-worker")
    thread.start()


def worker_status() -> dict:
    cfg = load_system_settings()["automation"]
    return {
        "enabled": bool(cfg["background_tasks"]),
        "interval_seconds": int(cfg["worker_interval_seconds"]),
        "worker_running": _worker_running,
        "monitor_running": _monitor_running,
    }


def _monitor_loop() -> None:
    global _monitor_running
    try:
        while True:
            cfg = load_system_settings()["automation"]
            if cfg["background_tasks"]:
                wake_worker()
            time.sleep(max(5, int(cfg["worker_interval_seconds"])))
    finally:
        _monitor_running = False


def start_worker_monitor() -> None:
    global _monitor_running
    if _monitor_running:
        return
    _monitor_running = True
    threading.Thread(
        target=_monitor_loop,
        daemon=True,
        name="miyori-task-monitor",
    ).start()
