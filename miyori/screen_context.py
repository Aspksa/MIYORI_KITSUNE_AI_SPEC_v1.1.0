"""Minimal client screen hints for chat, resolved only against owned records.

Last-opened UI elements are hints, not authorization. They do not change the
agent's tool permissions or provide raw HTML/document instructions.
"""
from __future__ import annotations

import re
from .db import get_document
from .document_intelligence import document_context_packet

MODULES = frozenset({
    "chat","documents","work","home","ai","actions","knowledge",
    "settings","account","mobile","update","garage","timesheet",
    "employees","contracts","invoice_offers",
})
_REFER = re.compile(
    r"(?i)(эт(?:от|ого|ому|ом)\s+(?:документ|файл|договор|сч[её]т)|"
    r"в\s+(?:открыт\w+|выбранн\w+)\s+(?:документ|файл|договор)|"
    r"по\s+нему|здесь\s+(?:указано|написано)|"
    r"что\s+здесь|из\s+него|в\s+этом\s+файле)"
)


def normalize_screen_context(project_id: int, payload: dict | None) -> dict:
    if not isinstance(payload,dict):
        return {}
    module=str(payload.get("module") or "").strip().lower()
    if module not in MODULES:
        return {}
    response={"module":module}
    doc_id=payload.get("document_id")
    if doc_id is not None:
        if module!="documents" or type(doc_id) is not int or doc_id <= 0:
            raise ValueError("Недопустимый документ в контексте экрана.")
        document=get_document(project_id,doc_id)
        if not document:
            raise ValueError("Документ из другого проекта или из корзины.")
        response["document_id"]=doc_id
        response["filename"]=document["filename"]
    return response


def resolve_screen_document(
    project_id: int, message: str, screen: dict,
) -> tuple[list[dict],list[dict]]:
    """Get a bounded excerpt only for explicit references to opened file."""
    if "document_id" not in screen or not _REFER.search(message[:1500]):
        return [],[]
    document_id=int(screen["document_id"])
    document=get_document(project_id,document_id)
    if not document:
        return [],[]
    packet=document_context_packet(project_id,document_id,message,max_chars=3200)
    items=[]
    for node in (packet.get("matches") or [])[:6]:
        text=str(node.get("text") or "").strip()[:1200]
        if not text:continue
        items.append({
            "filename":document["filename"],
            "chunk_index":node.get("locator") or node.get("node_index"),
            "content":text,
        })
    if not items and packet.get("summary"):
        items.append({
            "filename":document["filename"],
            "chunk_index":"stored_summary_only",
            "content":"Доступна только сохранённая сводка: "+
                     str(packet["summary"])[:1400],
        })
    if not items:
        items.append({
            "filename":document["filename"],
            "chunk_index":"extraction_unavailable",
            "content":"Содержание файла не подтверждено доступным текстом.",
        })
    source={
        "source_type":"screen_document",
        "document_id":document_id,
        "title":document["filename"],
        "download_url":
            f"/api/projects/{project_id}/documents/{document_id}/download",
        "coverage_warning":
            packet.get("extraction_status") not in ("complete","text_only"),
        "unverified":True,
    }
    return items,[source]
