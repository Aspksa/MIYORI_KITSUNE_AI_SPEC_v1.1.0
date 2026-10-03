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
from miyori.db import add_message, ensure_conversation, init_db, recent_messages
from miyori.provider import ProviderError, chat

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Miyori Kitsune AI", version="00.00.01")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: int | None = None


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
        "version": "00.00.01",
        "provider": "Cloud.ru Foundation Models",
        "provider_configured": bool(
            settings.cloudru_api_key and settings.cloudru_model_id
        ),
        "model_id": settings.cloudru_model_id or None,
        "storage": "SQLite",
    }


@app.post("/api/chat")
async def send_message(request: ChatRequest) -> dict:
    text = request.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Сообщение пустое.")

    conversation_id = ensure_conversation(request.conversation_id)
    add_message(conversation_id, "user", text)

    context = recent_messages(conversation_id)
    try:
        answer = await chat(context)
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
