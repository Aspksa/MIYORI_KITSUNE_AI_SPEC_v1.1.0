from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from miyori.config import settings
from miyori.db import (
    add_message,
    conversation_messages,
    create_project,
    ensure_conversation,
    get_project,
    init_db,
    list_conversations,
    list_projects,
    list_memory_facts,
    maybe_capture_user_memory,
    recent_messages,
    replace_memory_fact,
    search_verified_memory,
    update_memory_status,
    verified_memory_context,
)
from miyori.provider import ProviderError, chat

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Miyori Kitsune AI", version="00.00.04")
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


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {
        "name": "Miyori Kitsune AI",
        "version": "00.00.04",
        "provider": "Cloud.ru Foundation Models",
        "provider_configured": bool(
            settings.cloudru_api_key and settings.cloudru_model_id
        ),
        "model_id": settings.cloudru_model_id or None,
        "storage": "SQLite",
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

    context = recent_messages(conversation_id)
    memory_context = verified_memory_context(request.project_id, text)
    try:
        answer = await chat(context, memory_context=memory_context)
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
