from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from miyori.config import settings
from miyori.db import (
    add_message,
    conversation_messages,
    create_project,
    ensure_conversation,
    decide_permission_request,
    get_agent_trace,
    get_permission_request,
    get_project,
    init_db,
    add_document,
    create_task,
    development_snapshot,
    list_conversations,
    list_documents,
    list_projects,
    list_memory_facts,
    list_permission_requests,
    list_tasks,
    maybe_capture_user_memory,
    recent_messages,
    replace_memory_fact,
    search_document_chunks,
    recent_development_checks,
    request_task_cancel,
    search_verified_memory,
    update_memory_status,
    verified_memory_context,
)
from miyori.agent import run_agent
from miyori.background import register_background_handlers
from miyori.brain import build_context
from miyori.development import run_project_self_check
from miyori.documents import chunk_text, decode_document, safe_filename, save_original, sha256_bytes
from miyori.provider import ProviderError, chat
from miyori.persona import persona_metadata
from miyori.epistemic import (
    add_evidence,
    capture_user_claims,
    create_claim,
    create_source,
    epistemic_snapshot,
    get_claim as get_epistemic_claim,
    init_epistemic_db,
    list_claims as list_epistemic_claims,
    trusted_claim_context,
    verify_claim,
)
from miyori.tasks import wake_worker
from miyori.rag import init_rag, rag_status, retrieve as rag_retrieve
from miyori.tools import execute_approved_request, execute_tool, list_tools

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Miyori Kitsune AI", version="00.00.18")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    project_id: int
    conversation_id: int | None = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MemoryStatusRequest(BaseModel):
    status: str = Field(pattern="^(candidate|verified|disputed|superseded)$")


class MemoryReplaceRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=1000)


class ToolExecuteRequest(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


class TaskCreateRequest(BaseModel):
    task_type: str = Field(pattern="^(self_check|memory_consolidation|epistemic_review)$")
    payload: dict = Field(default_factory=dict)


class PermissionDecisionRequest(BaseModel):
    approved: bool


class ClaimCreateRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=1000)
    claim_type: str | None = Field(default=None, pattern="^(fact|preference|hypothesis|strategy)$")


class SourceCreateRequest(BaseModel):
    source_type: str = Field(pattern="^(user_message|document|tool|external|manual)$")
    source_key: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    locator: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, max_length=300)
    quality: float = Field(default=0.5, ge=0.0, le=1.0)
    independent_group: str | None = Field(default=None, max_length=300)
    metadata: dict = Field(default_factory=dict)


class EvidenceCreateRequest(BaseModel):
    source_id: int
    stance: str = Field(pattern="^(supports|contradicts|neutral)$")
    excerpt: str | None = Field(default=None, max_length=2000)
    weight: float = Field(default=1.0, ge=0.0, le=2.0)


@app.on_event("startup")
def startup() -> None:
    init_db()
    init_epistemic_db()
    init_rag()
    register_background_handlers()
    wake_worker()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {
        "name": "Miyori Kitsune AI",
        "version": "00.00.18",
        "persona": persona_metadata(),
        "provider": "Cloud.ru Foundation Models",
        "provider_configured": bool(
            settings.cloudru_api_key and settings.cloudru_model_id
        ),
        "model_id": settings.cloudru_model_id or None,
        "storage": "SQLite",
        "rag": rag_status(),
    }


@app.get("/api/projects")
def projects() -> dict:
    return {"projects": list_projects()}


@app.post("/api/projects")
def project_create(request: ProjectCreateRequest) -> dict:
    try:
        project = create_project(request.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"project": project}


@app.get("/api/projects/{project_id}/conversations")
def conversations(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"conversations": list_conversations(project_id)}


@app.get("/api/projects/{project_id}/conversations/{conversation_id}")
def conversation(project_id: int, conversation_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    items = conversation_messages(conversation_id, project_id)
    if not items:
        raise HTTPException(status_code=404, detail="Разговор не найден.")

    return {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "messages": items,
    }


@app.get("/api/projects/{project_id}/memory")
def memory(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"facts": list_memory_facts(project_id)}


@app.patch("/api/projects/{project_id}/memory/{fact_id}")
def memory_status(project_id: int, fact_id: int, request: MemoryStatusRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        fact = update_memory_status(project_id, fact_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not fact:
        raise HTTPException(status_code=404, detail="Факт не найден.")
    return {"fact": fact}


@app.get("/api/projects/{project_id}/memory/search")
def memory_search(project_id: int, q: str = "") -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"facts": search_verified_memory(project_id, q, limit=12)}


@app.post("/api/projects/{project_id}/memory/{fact_id}/replace")
def memory_replace(project_id: int, fact_id: int, request: MemoryReplaceRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        fact = replace_memory_fact(project_id, fact_id, request.statement)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"fact": fact}


@app.get("/api/projects/{project_id}/documents")
def documents(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"documents": list_documents(project_id)}


@app.post("/api/projects/{project_id}/documents")
async def document_upload(
    project_id: int,
    file: UploadFile = File(...),
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    filename = safe_filename(file.filename or "document.txt")
    data = await file.read()

    try:
        text = decode_document(filename, data)
        chunks = chunk_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not chunks:
        raise HTTPException(status_code=422, detail="В документе нет текста для усвоения.")

    digest = sha256_bytes(data)
    stored_path = save_original(project_id, filename, data, digest)
    document = add_document(
        project_id=project_id,
        filename=filename,
        stored_path=stored_path,
        mime_type=file.content_type,
        sha256=digest,
        size_bytes=len(data),
        chunks=chunks,
    )
    init_rag()
    return {
        "document": document,
        "chunk_count": len(chunks),
    }


@app.get("/api/projects/{project_id}/documents/search")
def document_search(project_id: int, q: str = "") -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"chunks": search_document_chunks(project_id, q, limit=12)}


@app.get("/api/projects/{project_id}/rag")
def rag_search(project_id: int, q: str = "", limit: int = 8) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    if not q.strip():
        raise HTTPException(status_code=422, detail="Пустой RAG-запрос.")
    result = rag_retrieve(
        project_id,
        q,
        limit=max(1, min(limit, 20)),
    )
    return result.to_dict()


@app.get("/api/projects/{project_id}/nexus")
def project_nexus(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден.")

    documents = list_documents(project_id)
    memory = list_memory_facts(project_id)
    permissions = list_permission_requests(project_id)
    tasks = list_tasks(project_id)
    development = development_snapshot(project_id)

    verified_memory = [item for item in memory if item.get("status") == "verified"]
    pending_permissions = [item for item in permissions if item.get("status") == "pending"]
    active_tasks = [item for item in tasks if item.get("status") in {"queued", "running"}]
    failed_tasks = [item for item in tasks if item.get("status") == "failed"]

    suggestions = []
    if pending_permissions:
        suggestions.append({
            "kind": "permission",
            "label": "Решить ожидающие действия",
            "detail": f"Ожидают решения: {len(pending_permissions)}",
        })
    if active_tasks:
        suggestions.append({
            "kind": "tasks",
            "label": "Проверить активные задачи",
            "detail": f"В работе или очереди: {len(active_tasks)}",
        })
    if failed_tasks:
        suggestions.append({
            "kind": "failed_tasks",
            "label": "Разобрать ошибки задач",
            "detail": f"Ошибок: {len(failed_tasks)}",
        })
    if documents:
        suggestions.append({
            "kind": "documents",
            "label": "Работать с материалами проекта",
            "detail": f"Документов: {len(documents)}",
        })
    if not suggestions:
        suggestions.append({
            "kind": "start",
            "label": "Начать новую задачу",
            "detail": "Опишите цель своими словами.",
        })

    return {
        "project": project,
        "counts": {
            "documents": len(documents),
            "verified_memory": len(verified_memory),
            "pending_permissions": len(pending_permissions),
            "active_tasks": len(active_tasks),
            "failed_tasks": len(failed_tasks),
            "checks_passed": development.get("checks_passed", 0),
            "checks_total": development.get("checks_total", 0),
        },
        "suggestions": suggestions[:3],
        "epistemic": epistemic_snapshot(project_id),
    }


@app.get("/api/projects/{project_id}/epistemic")
def epistemic_overview(project_id: int, status: str | None = None) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        claims = list_epistemic_claims(project_id, status=status, limit=100)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "snapshot": epistemic_snapshot(project_id),
        "claims": claims,
    }


@app.post("/api/projects/{project_id}/epistemic/claims")
def epistemic_claim_create(project_id: int, request: ClaimCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        claim = create_claim(
            project_id,
            request.statement,
            claim_type=request.claim_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"claim": claim}


@app.get("/api/projects/{project_id}/epistemic/claims/{claim_id}")
def epistemic_claim_get(project_id: int, claim_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    claim = get_epistemic_claim(project_id, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Утверждение не найдено.")
    return {"claim": claim}


@app.post("/api/projects/{project_id}/epistemic/sources")
def epistemic_source_create(project_id: int, request: SourceCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        source = create_source(
            project_id,
            request.source_type,
            source_key=request.source_key,
            title=request.title,
            locator=request.locator,
            publisher=request.publisher,
            quality=request.quality,
            independent_group=request.independent_group,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"source": source}


@app.post("/api/projects/{project_id}/epistemic/claims/{claim_id}/evidence")
def epistemic_evidence_create(
    project_id: int,
    claim_id: int,
    request: EvidenceCreateRequest,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        evidence = add_evidence(
            project_id,
            claim_id,
            request.source_id,
            request.stance,
            excerpt=request.excerpt,
            weight=request.weight,
        )
        verification = verify_claim(project_id, claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "evidence": evidence,
        "verification": verification.__dict__,
        "claim": get_epistemic_claim(project_id, claim_id),
    }


@app.post("/api/projects/{project_id}/epistemic/claims/{claim_id}/verify")
def epistemic_claim_verify(project_id: int, claim_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        result = verify_claim(project_id, claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "verification": result.__dict__,
        "claim": get_epistemic_claim(project_id, claim_id),
    }


@app.get("/api/tools")
def tools_catalog() -> dict:
    return {"tools": list_tools()}


@app.post("/api/projects/{project_id}/tools/execute")
def tool_execute(project_id: int, request: ToolExecuteRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        return execute_tool(request.name, project_id, request.arguments)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/permissions")
def permissions_list(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"requests": list_permission_requests(project_id)}


@app.post("/api/projects/{project_id}/permissions/{request_id}/decision")
def permission_decision(
    project_id: int,
    request_id: int,
    request: PermissionDecisionRequest,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    decided = decide_permission_request(project_id, request_id, request.approved)
    if not decided:
        raise HTTPException(status_code=409, detail="Запрос уже обработан или не найден.")

    if not request.approved:
        return {"request": decided}

    try:
        execution = execute_approved_request(project_id, request_id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "request": get_permission_request(project_id, request_id),
        "execution": execution,
    }


@app.get("/api/projects/{project_id}/tasks")
def tasks_list(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"tasks": list_tasks(project_id)}


@app.post("/api/projects/{project_id}/tasks")
def task_create(project_id: int, request: TaskCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    task = create_task(project_id, request.task_type, request.payload)
    wake_worker()
    return {"task": task}


@app.post("/api/projects/{project_id}/tasks/{task_id}/cancel")
def task_cancel(project_id: int, task_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    changed = request_task_cancel(project_id, task_id)
    if not changed:
        raise HTTPException(status_code=409, detail="Задачу уже нельзя отменить.")
    return {"cancel_requested": True}


@app.get("/api/projects/{project_id}/development")
def development(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {
        "snapshot": development_snapshot(project_id),
        "checks": recent_development_checks(project_id),
    }


@app.post("/api/projects/{project_id}/development/check")
def development_check(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    checks = run_project_self_check(project_id)
    return {
        "checks": [
            {"name": c.name, "passed": c.passed, "details": c.details}
            for c in checks
        ],
        "snapshot": development_snapshot(project_id),
    }


@app.get("/api/agent-runs/{run_id}")
def agent_trace(run_id: int) -> dict:
    trace = get_agent_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Agent run не найден.")
    return {"run": trace}


@app.post("/api/chat")
async def send_message(request: ChatRequest) -> dict:
    text = request.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Сообщение пустое.")
    if not get_project(request.project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    try:
        conversation_id = ensure_conversation(
            request.conversation_id,
            request.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    user_message_id = add_message(conversation_id, "user", text)
    maybe_capture_user_memory(
        request.project_id,
        conversation_id,
        user_message_id,
        text,
    )
    captured_claims = capture_user_claims(
        request.project_id,
        conversation_id,
        user_message_id,
        text,
    )

    context = recent_messages(conversation_id)
    brain = build_context(request.project_id, text)
    epistemic = trusted_claim_context(request.project_id, text, limit=6)
    rag = rag_retrieve(request.project_id, text, limit=8)
    agent = run_agent(request.project_id, conversation_id, text)
    try:
        answer = await chat(
            context,
            memory_context=None,
            document_context=None,
            brain_plan=brain.plan,
            tool_context=agent.tool_context,
            epistemic_context=None,
            rag_context=rag.to_dict(),
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(exc),
                "conversation_id": conversation_id,
            },
        ) from exc

    add_message(conversation_id, "assistant", answer)
    return {
        "conversation_id": conversation_id,
        "project_id": request.project_id,
        "answer": answer,
        "brain": {
            "plan": brain.plan,
            "memory_items": len(brain.memory),
            "document_items": len(brain.documents),
            "tools_allowed": brain.tools_allowed,
            "sources": [
                {
                    "filename": item.get("filename"),
                    "chunk_index": item.get("chunk_index"),
                    "content": item.get("content", "")[:360],
                }
                for item in brain.documents
            ],
        },
        "rag": rag.to_dict(),
        "epistemic": {
            "used_claims": [
                {
                    "id": item.get("id"),
                    "statement": item.get("statement"),
                    "status": item.get("status"),
                    "confidence": item.get("confidence"),
                    "claim_type": item.get("claim_type"),
                }
                for item in epistemic
            ],
            "captured_claim_ids": [item.get("id") for item in captured_claims],
            "snapshot": epistemic_snapshot(request.project_id),
        },
        "agent": {
            "run_id": agent.run_id,
            "actions": agent.actions,
            "steps_used": len(agent.actions),
            "max_steps": 3,
        },
    }


def open_browser() -> None:
    webbrowser.open(f"http://{settings.host}:{settings.port}")


if __name__ == "__main__":
    if settings.open_browser:
        threading.Timer(1.2, open_browser).start()
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
