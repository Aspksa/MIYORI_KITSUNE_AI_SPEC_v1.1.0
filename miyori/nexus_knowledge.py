from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .db import connect, get_project
from .document_intelligence import (
    init_document_intelligence_db,
)
from .document_questions import init_document_questions_db
from .epistemic import (
    epistemic_snapshot,
    get_claim,
    init_epistemic_db,
    list_claims,
)


NEXUS_KNOWLEDGE_SCHEMA_VERSION = "1.0.0"
KNOWLEDGE_SECTIONS = ("memory", "documents", "claims")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _normalized_terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}", value.casefold())
        if token
    }


def _matches(query_terms: set[str], *values: Any) -> bool:
    if not query_terms:
        return True
    haystack = " ".join(
        str(value or "")
        for value in values
        if value is not None
    ).casefold()
    return all(term in haystack for term in query_terms)


def _visible_memory(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                f.id,
                f.project_id AS origin_project_id,
                p.name AS origin_project_name,
                f.statement,
                f.status,
                f.confidence,
                f.verification_method,
                f.memory_scope,
                f.memory_kind,
                f.salience,
                f.observed_at,
                f.valid_from,
                f.valid_until,
                f.supersedes_fact_id,
                s.kind AS source_kind,
                s.conversation_id,
                s.message_id,
                s.locator AS source_locator
            FROM memory_facts f
            LEFT JOIN memory_sources s ON s.id = f.source_id
            LEFT JOIN projects p ON p.id = f.project_id
            WHERE f.memory_scope = 'user'
               OR (f.memory_scope = 'project' AND f.project_id = ?)
            ORDER BY
                CASE f.status
                    WHEN 'disputed' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'verified' THEN 2
                    ELSE 3
                END,
                f.id DESC
            """,
            (project_id,),
        ).fetchall()

    facts = [dict(row) for row in rows]
    active = [
        item
        for item in facts
        if item.get("status") in {"candidate", "verified", "disputed"}
    ]
    token_map = {
        int(item["id"]): _normalized_terms(str(item.get("statement") or ""))
        for item in active
    }
    for item in facts:
        item["possible_conflict_ids"] = []

    for index, left in enumerate(active):
        left_id = int(left["id"])
        left_terms = token_map[left_id]
        if len(left_terms) < 2:
            continue
        for right in active[index + 1 :]:
            right_id = int(right["id"])
            right_terms = token_map[right_id]
            shared = left_terms & right_terms
            if len(shared) < 2:
                continue
            if (left_terms - right_terms) and (right_terms - left_terms):
                left["possible_conflict_ids"].append(right_id)
                right["possible_conflict_ids"].append(left_id)

    return facts


def _document_rows(project_id: int) -> list[dict]:
    init_document_intelligence_db()
    init_document_questions_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.folder_id,
                f.name AS folder_name,
                d.filename,
                d.mime_type,
                d.sha256,
                d.size_bytes,
                d.created_at,
                (
                    SELECT COUNT(*)
                    FROM document_chunks c
                    WHERE c.document_id = d.id
                ) AS chunk_count,
                di.status AS intelligence_status,
                di.title AS intelligence_title,
                di.document_kind,
                di.language,
                di.word_count,
                di.page_count,
                di.section_count,
                di.table_count,
                di.node_count,
                di.coverage_ratio,
                di.extraction_status,
                di.extraction_coverage,
                di.extraction_warnings_json,
                di.summary_short,
                di.parser_version,
                di.analysis_model,
                di.last_error,
                di.updated_at AS intelligence_updated_at,
                (
                    SELECT COUNT(*)
                    FROM document_questions q
                    WHERE q.project_id = d.project_id
                      AND q.document_id = d.id
                ) AS exhaustive_questions,
                (
                    SELECT COUNT(*)
                    FROM document_questions q
                    WHERE q.project_id = d.project_id
                      AND q.document_id = d.id
                      AND q.status = 'complete'
                ) AS exhaustive_complete,
                (
                    SELECT COUNT(*)
                    FROM document_questions q
                    WHERE q.project_id = d.project_id
                      AND q.document_id = d.id
                      AND q.status IN ('queued','analyzing')
                ) AS exhaustive_active,
                (
                    SELECT MAX(q.overall_coverage_ratio)
                    FROM document_questions q
                    WHERE q.project_id = d.project_id
                      AND q.document_id = d.id
                ) AS best_exhaustive_coverage
            FROM documents d
            LEFT JOIN document_folders f ON f.id = d.folder_id
            LEFT JOIN document_intelligence di ON di.document_id = d.id
            WHERE d.project_id = ?
              AND d.deleted_at IS NULL
            ORDER BY d.id DESC
            """,
            (project_id,),
        ).fetchall()

    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["extraction_warnings"] = _loads(
            item.pop("extraction_warnings_json", None),
            [],
        )
        result.append(item)
    return result


def _claim_rows(project_id: int) -> list[dict]:
    init_epistemic_db()
    result: list[dict] = []
    for claim in list_claims(project_id, limit=300):
        detail = get_claim(project_id, int(claim["id"])) or claim
        evidence = list(detail.get("evidence") or [])
        groups = {
            str(item.get("independent_group") or f"source:{item.get('source_id')}")
            for item in evidence
        }
        previews = []
        for item in evidence[:6]:
            previews.append(
                {
                    "id": item.get("id"),
                    "stance": item.get("stance"),
                    "excerpt": item.get("excerpt"),
                    "weight": item.get("weight"),
                    "source": {
                        "id": item.get("source_id"),
                        "type": item.get("source_type"),
                        "key": item.get("source_key"),
                        "title": item.get("source_title"),
                        "locator": item.get("locator"),
                        "publisher": item.get("publisher"),
                        "quality": item.get("quality"),
                        "observed_at": item.get("observed_at"),
                    },
                }
            )
        result.append(
            {
                "id": int(claim["id"]),
                "statement": claim.get("statement"),
                "claim_type": claim.get("claim_type"),
                "status": claim.get("status"),
                "assessment": claim.get("assessment"),
                "confidence": float(claim.get("confidence") or 0.0),
                "supports": int(claim.get("supports") or 0),
                "contradictions": int(claim.get("contradictions") or 0),
                "open_contradictions": int(claim.get("open_contradictions") or 0),
                "independent_sources": len(groups),
                "evidence_count": len(evidence),
                "evidence_preview": previews,
                "created_at": claim.get("created_at"),
                "updated_at": claim.get("updated_at"),
                "verified_at": claim.get("verified_at"),
                "can_verify": claim.get("status") != "superseded",
            }
        )
    return result


def _memory_contract(item: dict) -> dict:
    conflict_ids = [int(value) for value in item.get("possible_conflict_ids") or []]
    return {
        "id": int(item["id"]),
        "statement": item.get("statement"),
        "status": item.get("status"),
        "scope": item.get("memory_scope"),
        "kind": item.get("memory_kind"),
        "confidence": item.get("confidence"),
        "salience": float(item.get("salience") or 0.0),
        "verification_method": item.get("verification_method"),
        "observed_at": item.get("observed_at"),
        "valid_from": item.get("valid_from"),
        "valid_until": item.get("valid_until"),
        "possible_conflict_ids": conflict_ids,
        "provenance": {
            "source_kind": item.get("source_kind"),
            "conversation_id": item.get("conversation_id"),
            "message_id": item.get("message_id"),
            "locator": item.get("source_locator"),
            "origin_project_id": item.get("origin_project_id"),
            "origin_project_name": item.get("origin_project_name"),
        },
        "actions": {
            "verify": item.get("status") != "verified",
            "dispute": item.get("status") not in {"disputed", "superseded"},
            "supersede": item.get("status") != "superseded",
        },
    }


def _document_contract(item: dict) -> dict:
    intelligence_status = item.get("intelligence_status") or "not_indexed"
    extraction_status = item.get("extraction_status") or "unknown"
    extraction_coverage = float(item.get("extraction_coverage") or 0.0)
    knowledge_coverage = float(item.get("coverage_ratio") or 0.0)
    warnings = list(item.get("extraction_warnings") or [])
    limited = (
        intelligence_status in {"partial", "needs_ocr", "unsupported", "failed"}
        or extraction_status in {"partial", "text_only", "needs_ocr", "unavailable"}
        or extraction_coverage < 0.999
    )
    can_analyze = (
        intelligence_status not in {"needs_ocr", "unsupported"}
        and extraction_status not in {"needs_ocr", "unavailable"}
        and int(item.get("chunk_count") or 0) > 0
    )
    return {
        "id": int(item["id"]),
        "filename": item.get("filename"),
        "folder_id": item.get("folder_id"),
        "folder_name": item.get("folder_name"),
        "mime_type": item.get("mime_type"),
        "size_bytes": int(item.get("size_bytes") or 0),
        "created_at": item.get("created_at"),
        "provenance": {
            "sha256": item.get("sha256"),
            "locator": f"document:{int(item['id'])}",
            "source_kind": "original_document",
        },
        "index": {
            "chunks": int(item.get("chunk_count") or 0),
            "nodes": int(item.get("node_count") or 0),
            "parser_version": item.get("parser_version"),
        },
        "intelligence": {
            "status": intelligence_status,
            "title": item.get("intelligence_title"),
            "document_kind": item.get("document_kind"),
            "language": item.get("language"),
            "summary": item.get("summary_short"),
            "word_count": int(item.get("word_count") or 0),
            "page_count": int(item.get("page_count") or 0),
            "section_count": int(item.get("section_count") or 0),
            "table_count": int(item.get("table_count") or 0),
            "coverage": knowledge_coverage,
            "extraction_status": extraction_status,
            "extraction_coverage": extraction_coverage,
            "warnings": warnings,
            "analysis_model": item.get("analysis_model"),
            "last_error": item.get("last_error"),
            "updated_at": item.get("intelligence_updated_at"),
            "limited": limited,
        },
        "exhaustive": {
            "questions": int(item.get("exhaustive_questions") or 0),
            "complete": int(item.get("exhaustive_complete") or 0),
            "active": int(item.get("exhaustive_active") or 0),
            "best_coverage": float(item.get("best_exhaustive_coverage") or 0.0),
        },
        "actions": {
            "analyze": can_analyze,
            "rebuild": True,
        },
    }


def build_nexus_knowledge_center(
    project_id: int,
    *,
    query: str = "",
    limit: int = 80,
) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError("Проект не найден.")

    limit = max(1, min(int(limit), 200))
    clean_query = " ".join(str(query or "").strip().split())[:300]
    terms = _normalized_terms(clean_query)

    memory_all = [_memory_contract(item) for item in _visible_memory(project_id)]
    documents_all = [_document_contract(item) for item in _document_rows(project_id)]
    claims_all = _claim_rows(project_id)

    memory = [
        item
        for item in memory_all
        if _matches(
            terms,
            item.get("statement"),
            item.get("status"),
            item.get("scope"),
            item.get("kind"),
            (item.get("provenance") or {}).get("origin_project_name"),
        )
    ][:limit]

    documents = [
        item
        for item in documents_all
        if _matches(
            terms,
            item.get("filename"),
            item.get("folder_name"),
            (item.get("intelligence") or {}).get("title"),
            (item.get("intelligence") or {}).get("summary"),
            (item.get("intelligence") or {}).get("document_kind"),
        )
    ][:limit]

    claims = [
        item
        for item in claims_all
        if _matches(
            terms,
            item.get("statement"),
            item.get("status"),
            item.get("assessment"),
            item.get("claim_type"),
            " ".join(
                str((preview.get("source") or {}).get("title") or "")
                for preview in item.get("evidence_preview") or []
            ),
        )
    ][:limit]

    memory_counts = {
        status: sum(1 for item in memory_all if item.get("status") == status)
        for status in ("candidate", "verified", "disputed", "superseded")
    }
    memory_conflicts = sum(
        1 for item in memory_all if item.get("possible_conflict_ids")
    )
    document_limited = sum(
        1
        for item in documents_all
        if bool((item.get("intelligence") or {}).get("limited"))
    )
    document_processing = sum(
        1
        for item in documents_all
        if (item.get("intelligence") or {}).get("status")
        in {"queued", "analyzing"}
        or int((item.get("exhaustive") or {}).get("active") or 0) > 0
    )
    epi = epistemic_snapshot(project_id)
    claim_counts = dict(epi.get("claims") or {})
    claim_disputed = int(claim_counts.get("disputed") or 0)
    claim_needs_evidence = int(claim_counts.get("candidate") or 0)
    open_contradictions = int(epi.get("open_contradictions") or 0)

    attention = {
        "memory_conflicts": memory_conflicts,
        "memory_disputed": int(memory_counts.get("disputed") or 0),
        "documents_limited": document_limited,
        "documents_processing": document_processing,
        "claim_disputed": claim_disputed,
        "claim_open_contradictions": open_contradictions,
        "claims_need_evidence": claim_needs_evidence,
    }
    attention["total"] = (
        attention["memory_conflicts"]
        + attention["memory_disputed"]
        + attention["documents_limited"]
        + attention["claim_disputed"]
        + attention["claim_open_contradictions"]
    )

    return {
        "schema_version": NEXUS_KNOWLEDGE_SCHEMA_VERSION,
        "project": {
            "id": int(project["id"]),
            "name": project["name"],
            "kind": project.get("kind"),
        },
        "query": clean_query,
        "counts": {
            "memory": {
                **memory_counts,
                "visible": len(memory_all),
                "conflicts": memory_conflicts,
            },
            "documents": {
                "total": len(documents_all),
                "limited": document_limited,
                "processing": document_processing,
                "average_extraction_coverage": (
                    round(
                        sum(
                            float((item.get("intelligence") or {}).get("extraction_coverage") or 0.0)
                            for item in documents_all
                        )
                        / len(documents_all),
                        4,
                    )
                    if documents_all
                    else 0.0
                ),
                "average_knowledge_coverage": (
                    round(
                        sum(
                            float((item.get("intelligence") or {}).get("coverage") or 0.0)
                            for item in documents_all
                        )
                        / len(documents_all),
                        4,
                    )
                    if documents_all
                    else 0.0
                ),
            },
            "claims": {
                **claim_counts,
                "total": len(claims_all),
                "sources": int(epi.get("sources") or 0),
                "open_contradictions": open_contradictions,
            },
            "attention": attention,
        },
        "results": {
            "memory": len(memory),
            "documents": len(documents),
            "claims": len(claims),
        },
        "memory": memory,
        "documents": documents,
        "claims": claims,
        "semantics": {
            "sections_are_distinct": True,
            "memory_meaning": "remembered contextual facts and preferences",
            "documents_meaning": "original project materials and extraction/analysis coverage",
            "claims_meaning": "claims assessed from explicit evidence",
            "graph_is_optional": True,
            "arbitrary_model_markup": False,
        },
        "generated_at": _now(),
    }
