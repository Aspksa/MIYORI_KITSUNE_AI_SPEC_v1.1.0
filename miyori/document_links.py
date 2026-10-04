"""Read-only, project-local candidate document links with precise provenance.

No LLM claims, guessed legal relationships, fuzzy matching, write tools,
or untrusted document instructions. Only exact typed identifiers are matched.
Results describe *candidates*, not established links or facts.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .db import connect, get_document


# Context is mandatory for contract/invoice numbers to avoid matching arbitrary
# quantities and dates from an unrelated file.
_REG = re.compile(
    r"(?<![А-ЯЁ\w])([АВЕКМНОРСТУХ]\s*\d{3}\s*[АВЕКМНОРСТУХ]{2}\s*\d{2,3})(?![А-ЯЁ\w])",
    re.IGNORECASE,
)
_VIN = re.compile(
    r"\b(?:VIN|ВИН|номер\s+кузова)\s*(?:№|#|:)?\s*([A-HJ-NPR-Z0-9]{17})(?![A-Z0-9])",
    re.IGNORECASE,
)
_CONTRACT = re.compile(
    r"\b(?:договор(?:а|у|ом)?|контракт(?:а|у|ом)?)\s*"
    r"(?:[№#]|N(?:o|r)?\.?\s*)\s*([А-ЯЁA-Z0-9][А-ЯЁA-Z0-9/._-]{3,32})",
    re.IGNORECASE,
)
_INVOICE = re.compile(
    r"\b(?:сч[её]т(?:а|у|ом)?(?:[-\s]+оферт\w*)?)\s*"
    r"(?:[№#]|N(?:o|r)?\.?\s*)\s*([А-ЯЁA-Z0-9][А-ЯЁA-Z0-9/._-]{3,32})",
    re.IGNORECASE,
)
_MAX_NODES = 8000
_MAX_DOCS = 500


def extract_identifiers(text: str) -> list[tuple[str, str]]:
    """Strong text references only, normalized and bounded."""
    source = str(text or "")[:12000]
    result: set[tuple[str, str]] = set()
    for pattern, category in (
        (_REG, "registration"),
        (_VIN, "vin"),
        (_CONTRACT, "contract_number"),
        (_INVOICE, "invoice_number"),
    ):
        for match in pattern.finditer(source):
            raw = match.group(1)
            value = re.sub(r"\s+", "", raw).upper()
            if category in {"contract_number", "invoice_number"}:
                value = value.strip(".,;:-_")
                # Reject date-like and pure numeric identifiers commonly
                # shared across unrelated invoice tables.
                if len(value) < 4 or value.isdigit():
                    continue
            elif category == "vin":
                if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
                    continue
            if value:
                result.add((category, value))
            if len(result) >= 60:
                break
    return sorted(result)


def related_documents(
    project_id: int, document_id: int, *, limit: int = 8,
) -> dict:
    """Provenance in both files, no links to deleted/foreign documents.

    Returns a partial-result indicator when the bounded node scan is hit.
    """
    original = get_document(project_id, document_id)
    if not original:
        raise LookupError("Документ не найден в выбранном проекте.")
    with connect() as db:
        nodes = db.execute(
            """
            SELECT n.document_id, n.locator, n.text, d.filename
            FROM document_nodes n
            JOIN documents d ON d.id=n.document_id
            WHERE n.project_id=? AND d.project_id=? AND d.deleted_at IS NULL
            ORDER BY n.document_id, n.node_index
            LIMIT ?
            """,
            (project_id,project_id,_MAX_NODES+1),
        ).fetchall()
        doc_count = db.execute(
            "SELECT COUNT(*) FROM documents WHERE project_id=? AND deleted_at IS NULL",
            (project_id,),
        ).fetchone()[0]
    truncated = len(nodes) > _MAX_NODES or doc_count > _MAX_DOCS
    if len(nodes) > _MAX_NODES:
        nodes=nodes[:_MAX_NODES]
    values: dict[tuple[str,str],dict[int,list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in nodes:
        for label,value in extract_identifiers(row["text"]):
            records = values[(label,value)][int(row["document_id"])]
            if len(records) < 3:
                records.append({
                    "locator":str(row["locator"])[:180],
                    "excerpt":str(row["text"])[:300],
                })
    candidates: dict[int,dict] = {}
    for (kind,identifier),documents in values.items():
        primary=documents.get(document_id)
        if not primary:
            continue
        for target_id,evidence in documents.items():
            if target_id == document_id:
                continue
            # Cap per target and prefer a small number of strongest typed
            # identifiers; repeated words never inflate evidence.
            obj=candidates.setdefault(target_id,{
                "document_id":target_id,"match_count":0,"matches":[],
            })
            obj["match_count"] += 1
            if len(obj["matches"]) < 8:
                obj["matches"].append({
                    "kind":kind,"identifier":identifier,
                    "source":primary[0],"target":evidence[0],
                })
    names: dict[int,str] = {
        int(row["document_id"]): str(row["filename"])
        for row in nodes
    }
    result=sorted(candidates.values(),key=lambda item:(
        -item["match_count"],item["document_id"],
    ))[:max(1,min(int(limit),30))]
    for item in result:
        item["filename"]=names.get(item["document_id"],"Документ")
    return {
        "project_id":project_id,
        "source_document_id":document_id,
        "filename":original["filename"],
        "candidates":result,
        "candidate_count":len(candidates),
        "scan_truncated":truncated,
        "verified_relationship":False,
        "status":"candidate_matches_only",
        "note":(
            "Найдены только совпадения явно указанных идентификаторов "
            "в доступном извлечённом тексте с местами в обоих файлах. "
            "Это возможные связи, а не юридическое подтверждение "
            "отношений, полноты OCR или правильности документов."
        ),
    }
