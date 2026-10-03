from __future__ import annotations

import math
import re
import sqlite3
from dataclasses import dataclass, asdict
from typing import Iterable

from .db import connect, search_document_chunks, search_verified_memory
from .epistemic import trusted_claim_context


RRF_K = 60.0
DEFAULT_LIMIT = 8
DEFAULT_CONTEXT_CHARS = 12000
MAX_ITEM_CHARS = 2400


@dataclass
class RAGItem:
    key: str
    source_type: str
    title: str
    content: str
    score: float
    locator: str | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RAGContext:
    query: str
    items: list[RAGItem]
    retrieval_mode: str
    total_chars: int
    candidates_seen: int

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "items": [item.to_dict() for item in self.items],
            "retrieval_mode": self.retrieval_mode,
            "total_chars": self.total_chars,
            "candidates_seen": self.candidates_seen,
        }


def _tokens(text: str) -> list[str]:
    stop = {
        "что", "это", "как", "для", "или", "при", "под", "над", "без", "есть",
        "был", "была", "будет", "мне", "мой", "моя", "мои", "твой", "твоя",
        "так", "уже", "ещё", "очень", "можно", "нужно", "надо", "если",
        "когда", "где", "чем", "какой", "какая", "какие", "который",
    }
    return [
        token for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}", text.lower())
        if token not in stop
    ]


def _fts_query(query: str) -> str:
    tokens = _tokens(query)[:12]
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)


def init_rag() -> dict:
    """Create/sync local FTS index. Falls back cleanly if FTS5 is unavailable."""
    try:
        with connect() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_document_fts USING fts5(
                    content,
                    filename UNINDEXED,
                    document_id UNINDEXED,
                    chunk_id UNINDEXED,
                    chunk_index UNINDEXED,
                    project_id UNINDEXED,
                    tokenize='unicode61'
                )
                """
            )
            conn.execute("DELETE FROM rag_document_fts")
            conn.execute(
                """
                INSERT INTO rag_document_fts(
                    content, filename, document_id, chunk_id, chunk_index, project_id
                )
                SELECT
                    dc.content, d.filename, d.id, dc.id, dc.chunk_index, d.project_id
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                """
            )
            count = conn.execute("SELECT COUNT(*) AS count FROM rag_document_fts").fetchone()["count"]
        return {"fts5": True, "indexed_chunks": int(count)}
    except sqlite3.OperationalError:
        return {"fts5": False, "indexed_chunks": 0}


def rag_status() -> dict:
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM rag_document_fts"
            ).fetchone()
        return {"fts5": True, "indexed_chunks": int(row["count"])}
    except sqlite3.OperationalError:
        return {"fts5": False, "indexed_chunks": 0}


def _document_fts(project_id: int, query: str, limit: int = 20) -> list[RAGItem]:
    match = _fts_query(query)
    if not match:
        return []
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    chunk_id,
                    document_id,
                    chunk_index,
                    filename,
                    content,
                    bm25(rag_document_fts, 1.0) AS rank
                FROM rag_document_fts
                WHERE rag_document_fts MATCH ? AND project_id = ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (match, str(project_id), limit),
            ).fetchall()
    except sqlite3.OperationalError:
        return []

    items = []
    for row in rows:
        items.append(
            RAGItem(
                key=f"doc:{row['filename']}:{row['chunk_index']}",
                source_type="document",
                title=row["filename"],
                content=row["content"][:MAX_ITEM_CHARS],
                score=0.0,
                locator=f"document:{row['document_id']}/chunk:{row['chunk_index']}",
                metadata={
                    "document_id": int(row["document_id"]),
                    "chunk_id": int(row["chunk_id"]),
                    "chunk_index": int(row["chunk_index"]),
                    "fts_rank": float(row["rank"]),
                },
            )
        )
    return items


def _document_lexical(project_id: int, query: str, limit: int = 20) -> list[RAGItem]:
    rows = search_document_chunks(project_id, query, limit=limit)
    items = []
    for row in rows:
        items.append(
            RAGItem(
                key=f"doc:{row.get('filename')}:{row.get('chunk_index')}",
                source_type="document",
                title=row.get("filename") or "Документ",
                content=str(row.get("content", ""))[:MAX_ITEM_CHARS],
                score=0.0,
                locator=f"document:{row.get('document_id', '')}/chunk:{row.get('chunk_index', '')}",
                metadata={
                    "document_id": row.get("document_id"),
                    "chunk_id": row.get("id"),
                    "chunk_index": row.get("chunk_index"),
                },
            )
        )
    return items


def _memory(project_id: int, query: str, limit: int = 12) -> list[RAGItem]:
    rows = search_verified_memory(project_id, query, limit=limit)
    query_tokens = set(_tokens(query))
    items = []
    for row in rows:
        statement = row["statement"]
        statement_tokens = set(_tokens(statement))
        if query_tokens and not (query_tokens & statement_tokens):
            continue
        items.append(
            RAGItem(
                key=f"memory:{row['id']}",
                source_type="memory",
                title="Подтверждённая память",
                content=statement[:MAX_ITEM_CHARS],
                score=0.0,
                locator=f"memory:{row['id']}",
                metadata={"memory_id": row["id"], "observed_at": row.get("observed_at")},
            )
        )
    return items


def _knowledge(project_id: int, query: str, limit: int = 12) -> list[RAGItem]:
    rows = trusted_claim_context(project_id, query, limit=limit)
    return [
        RAGItem(
            key=f"claim:{row['id']}",
            source_type="knowledge",
            title=f"Знание · {row['status']}",
            content=row["statement"][:MAX_ITEM_CHARS],
            score=0.0,
            locator=f"claim:{row['id']}",
            metadata={
                "claim_id": row["id"],
                "status": row["status"],
                "confidence": row.get("confidence"),
                "claim_type": row.get("claim_type"),
            },
        )
        for row in rows
    ]


def _rrf_merge(rankings: list[tuple[str, list[RAGItem], float]]) -> list[RAGItem]:
    merged: dict[str, RAGItem] = {}
    scores: dict[str, float] = {}

    for channel, items, weight in rankings:
        for rank, item in enumerate(items, start=1):
            if item.key not in merged:
                merged[item.key] = item
                scores[item.key] = 0.0
            scores[item.key] += weight / (RRF_K + rank)
            metadata = merged[item.key].metadata or {}
            channels = list(metadata.get("retrieval_channels", []))
            if channel not in channels:
                channels.append(channel)
            metadata["retrieval_channels"] = channels
            merged[item.key].metadata = metadata

    for key, item in merged.items():
        item.score = round(scores[key], 8)

    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


def _dedupe(items: Iterable[RAGItem]) -> list[RAGItem]:
    seen_text: set[str] = set()
    result: list[RAGItem] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item.content.lower()).strip()
        fingerprint = normalized[:500]
        if not fingerprint or fingerprint in seen_text:
            continue
        seen_text.add(fingerprint)
        result.append(item)
    return result


def retrieve(
    project_id: int,
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_context_chars: int = DEFAULT_CONTEXT_CHARS,
) -> RAGContext:
    clean_query = " ".join(query.strip().split())
    if not clean_query:
        return RAGContext(query="", items=[], retrieval_mode="empty", total_chars=0, candidates_seen=0)

    fts = _document_fts(project_id, clean_query, limit=max(limit * 3, 12))
    lexical = _document_lexical(project_id, clean_query, limit=max(limit * 3, 12))
    memory = _memory(project_id, clean_query, limit=max(limit * 2, 8))
    knowledge = _knowledge(project_id, clean_query, limit=max(limit * 2, 8))

    rankings = [
        ("document_fts", fts, 1.15),
        ("document_lexical", lexical, 1.0),
        ("verified_memory", memory, 0.95),
        ("epistemic_knowledge", knowledge, 1.1),
    ]
    merged = _dedupe(_rrf_merge(rankings))
    candidates_seen = len(merged)

    selected: list[RAGItem] = []
    total_chars = 0
    per_type: dict[str, int] = {}
    soft_caps = {"document": 5, "memory": 3, "knowledge": 4}

    for item in merged:
        if len(selected) >= max(1, min(limit, 20)):
            break
        if per_type.get(item.source_type, 0) >= soft_caps.get(item.source_type, limit):
            continue

        remaining = max_context_chars - total_chars
        if remaining <= 0:
            break
        content = item.content[: min(MAX_ITEM_CHARS, remaining)]
        if len(content) < 20:
            continue
        item.content = content
        selected.append(item)
        total_chars += len(content)
        per_type[item.source_type] = per_type.get(item.source_type, 0) + 1

    mode = "hybrid_fts_rrf" if fts else "hybrid_lexical_rrf"
    return RAGContext(
        query=clean_query,
        items=selected,
        retrieval_mode=mode,
        total_chars=total_chars,
        candidates_seen=candidates_seen,
    )
