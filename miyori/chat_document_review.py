"""Cautious evidence-only comparison of project-owned document text chunks.

Values are observed strings, never authoritative contradictions. A limited
scan cannot claim to verify the entire original (especially scanned PDFs).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .db import connect
from .document_intelligence import get_document_intelligence

MAX_FILES = 5
MAX_CHUNKS_PER_FILE = 160
MAX_CHARS_PER_FILE = 450_000
MAX_OBSERVATIONS_PER_FIELD = 16

_PATTERNS = {
    "ИНН": re.compile(r"\bИНН[\s:№\-]*([0-9]{10}|[0-9]{12})\b", re.I),
    "НДС": re.compile(r"\bНДС[\s:№\-]*(\d{1,2}(?:[.,]\d+)?)\s*%", re.I),
    "Сумма": re.compile(
        r"(?<!\w)((?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d{2})?)\s*(?:₽|руб\.?|рублей|рубля)\b", re.I
    ),
    "Дата": re.compile(r"\b(\d{1,2}\.\d{1,2}\.(?:19|20)\d{2})\b"),
    "Госномер": re.compile(r"\b([АВЕКМНОРСТУХ]\s*\d{3}\s*[АВЕКМНОРСТУХ]{2}\s*\d{2,3})\b", re.I),
    "VIN": re.compile(r"\bVIN\s*(?:[:№\-]\s*)?([A-HJ-NPR-Z0-9]{17})\b", re.I),
}
_DISPLAY = {
    "ИНН":"ИНН","НДС":"НДС","Сумма":"Денежные суммы",
    "Дата":"Даты","Госномер":"Госномера","VIN":"VIN",
}


def _normalize(kind: str, raw: str) -> str | None:
    text=raw.strip()
    if kind=="Дата":
        try:
            value=datetime.strptime(text,"%d.%m.%Y")
            return value.strftime("%d.%m.%Y")
        except ValueError:
            return None
    if kind=="Сумма":
        clean=text.replace("\u00a0","").replace(" ","").replace(",",".")
        try:
            return f"{Decimal(clean):.2f}"
        except InvalidOperation:
            return None
    if kind=="НДС":
        return text.replace(",",".")+"%"
    if kind in ("VIN","Госномер"):
        return re.sub(r"\s+","",text).upper()
    return text


def _scan_text(filename: str, document_id: int, chunk_index: int,
               text: str, observations: dict) -> None:
    for kind,regex in _PATTERNS.items():
        current=observations.setdefault(kind,[])
        if len(current)>=MAX_OBSERVATIONS_PER_FIELD:
            continue
        for found in regex.finditer(text):
            normalized=_normalize(kind,found.group(1))
            if normalized is None:
                continue
            if any(x["value"]==normalized for x in current):
                continue
            # Each entry is supported by an exact 120-char quote and index.
            quote=text[max(0,found.start()-58):min(len(text),found.end()+58)]
            quote=" ".join(quote.split())[:140]
            current.append({
                "value":normalized,
                "document_id":document_id,
                "filename":filename,
                "chunk_index":chunk_index,
                "excerpt":quote,
            })
            if len(current)>=MAX_OBSERVATIONS_PER_FIELD:
                break


def compare_project_documents(project_id: int, document_ids: list[int]) -> dict:
    if len(document_ids)<2 or len(document_ids)>MAX_FILES or len(document_ids)!=len(set(document_ids)):
        raise ValueError("Для сравнения выберите от двух до пяти разных документов.")
    checked=[]
    for doc_id in document_ids:
        with connect() as conn:
            doc=conn.execute(
                "SELECT id,filename FROM documents "
                "WHERE id=? AND project_id=? AND deleted_at IS NULL",
                (int(doc_id),project_id),
            ).fetchone()
            if not doc:
                raise ValueError("Документ не принадлежит выбранному проекту.")
            total=int(conn.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE document_id=?",
                (doc_id,),
            ).fetchone()[0])
            chunks=conn.execute(
                "SELECT chunk_index,content FROM document_chunks "
                "WHERE document_id=? ORDER BY chunk_index ASC LIMIT ?",
                (doc_id,MAX_CHUNKS_PER_FILE+1),
            ).fetchall()
        observations={}
        chars=0
        scanned=0
        # Never claim full coverage of the original; this bounds text scan.
        for item in chunks[:MAX_CHUNKS_PER_FILE]:
            full=str(item["content"] or "")
            available=max(0,MAX_CHARS_PER_FILE-chars)
            if not available:
                break
            sample=full[:available]
            chars+=len(sample)
            scanned+=1
            _scan_text(doc["filename"],int(doc_id),int(item["chunk_index"]),
                       sample,observations)
            if len(sample)<len(full):
                break
        profile=get_document_intelligence(project_id,int(doc_id))
        status=profile.get("extraction_status") if profile else None
        coverage=profile.get("extraction_coverage") if profile else None
        # "fully_scanned" is only about stored TEXT chunks.
        full_text_scan=bool(total and scanned>=total and (
            len(chunks)<=MAX_CHUNKS_PER_FILE
        ) and chars<MAX_CHARS_PER_FILE)
        checked.append({
            "document_id":int(doc_id),
            "filename":doc["filename"],
            "text_chunks_scanned":scanned,
            "text_chunks_total":total,
            "stored_text_scanned":full_text_scan,
            "source_extraction_status":status or "not_verified",
            "source_extraction_coverage":coverage,
            "requires_ocr":total==0,
            "observations":observations,
        })

    differences=[]
    for kind in _PATTERNS:
        reported=[(doc,list(doc["observations"].get(kind,[])))
                  for doc in checked if doc["observations"].get(kind)]
        if len(reported)<2:
            continue
        groups={tuple(sorted({v["value"] for v in values}))
                for _,values in reported}
        if len(groups)<=1:
            continue
        differences.append({
            "field":_DISPLAY[kind],
            "interpretation":"Наблюдаются разные значения. Это не доказанное противоречие.",
            "evidence":[{
                "document_id":doc["document_id"],
                "filename":doc["filename"],
                "values":values[:4],
            } for doc,values in reported],
        })
    return {
        "schema_version":"1.0.0",
        "project_id":project_id,
        "documents":checked,
        "potential_differences":differences,
        "difference_count":len(differences),
        "all_stored_text_scanned":all(x["stored_text_scanned"] for x in checked),
        "original_fully_verified":False,
        "fact_verified":False,
        "note":(
            "Сравнивались только доступные текстовые фрагменты. "
            "Сканирование не заменяет семантическую проверку договора, OCR "
            "или полную проверку страниц. Разные числа/даты могут быть правомерными."
        ),
    }
