from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class AnswerSource:
    source_type: str
    title: str
    locator: str | None
    document_id: int | None = None
    chunk_indexes: tuple[int, ...] = ()

    def to_dict(self, project_id: int) -> dict:
        data = asdict(self)
        data["chunk_indexes"] = list(self.chunk_indexes)
        if self.source_type == "document" and self.document_id is not None:
            data["download_url"] = (
                f"/api/projects/{project_id}/documents/{self.document_id}/download"
            )
        else:
            data["download_url"] = None
        return data


def build_answer_sources(
    project_id: int,
    rag_context: dict | None,
    tool_context: list[dict] | None = None,
) -> list[dict]:
    documents: dict[int, dict] = {}

    for item in (rag_context or {}).get("items", []):
        if item.get("source_type") != "document":
            continue
        metadata = item.get("metadata") or {}
        document_id = metadata.get("document_id")
        if document_id is None:
            continue
        document_id = int(document_id)
        entry = documents.setdefault(document_id, {
            "title": item.get("title") or "Документ",
            "locator": item.get("locator"),
            "chunks": set(),
        })
        chunk_index = metadata.get("chunk_index")
        if chunk_index is not None:
            entry["chunks"].add(int(chunk_index))

    for action in tool_context or []:
        tool_name = action.get("tool")
        if tool_name not in {
            "project_document_search",
            "project_document_read",
            "project_document_understanding",
            "project_document_outline",
            "project_document_deep_search",
            "project_document_exhaustive_question",
            "project_document_question_status",
        }:
            continue
        result = action.get("result") or {}

        if tool_name == "project_document_outline":
            candidates: Iterable[dict] = [{
                "document_id": result.get("document_id"),
                "filename": result.get("filename"),
                "locator": (
                    (result.get("outline") or [{}])[0].get("locator")
                    if result.get("outline") else None
                ),
            }]
        elif tool_name in {
            "project_document_understanding",
            "project_document_deep_search",
        }:
            document = result.get("document") or {}
            context = result.get("context") or {}
            matches = context.get("matches") or result.get("nodes") or []
            locator = next(
                (item.get("locator") for item in matches if isinstance(item, dict) and item.get("matched")),
                None,
            )
            candidates = [{
                "document_id": document.get("id"),
                "filename": document.get("filename"),
                "locator": locator,
            }]
        elif tool_name in {
            "project_document_exhaustive_question",
            "project_document_question_status",
        }:
            document = result.get("document") or {}
            question = result.get("question") or {}
            answer = question.get("answer") or {}
            evidence = answer.get("evidence") or []
            locator = next(
                (
                    item.get("locator")
                    for item in evidence
                    if isinstance(item, dict) and item.get("locator")
                ),
                None,
            )
            candidates = [{
                "document_id": document.get("id"),
                "filename": document.get("filename"),
                "locator": locator or f"document:{document.get('id')}:exhaustive",
            }]
        else:
            candidates = (
                result.get("chunks")
                or result.get("documents")
                or ([result.get("document")] if result.get("document") else [])
            )

        for item in candidates:
            if not isinstance(item, dict):
                continue
            document_id = item.get("document_id") or item.get("id")
            filename = item.get("filename")
            if document_id is None or not filename:
                continue
            document_id = int(document_id)
            entry = documents.setdefault(document_id, {
                "title": filename,
                "locator": item.get("locator") or f"document:{document_id}",
                "chunks": set(),
            })
            if item.get("locator") and not entry.get("locator"):
                entry["locator"] = item["locator"]
            chunk_index = item.get("chunk_index")
            if chunk_index is not None:
                entry["chunks"].add(int(chunk_index))

    result = []
    for document_id, item in documents.items():
        source = AnswerSource(
            source_type="document",
            title=str(item["title"]),
            locator=item.get("locator"),
            document_id=document_id,
            chunk_indexes=tuple(sorted(item["chunks"])),
        )
        result.append(source.to_dict(project_id))

    result.sort(key=lambda item: item["title"].lower())
    return result
