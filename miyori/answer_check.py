"""Numerical source-consistency guard for Miyori answers.

A matching number in an extract is *not* semantic or factual verification.
Warn on missing exact numerical references; never rewrite the model answer or
infer a contradiction from a mere difference in retrieved texts.
"""
from __future__ import annotations
import re

_NUMBERS=re.compile(r"(?<![\w])(?:\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)")
_SENTENCES=re.compile(r"(?:\n+|;\s*|(?<=[.!?])\s+(?=[А-ЯЁA-Z]))")
_WORDS=re.compile(r"[а-яёa-z]{4,}",re.IGNORECASE)
_IGNORE={"сумма","рубля","рублей","цена","дата","также","когда",
         "этого","здесь","проекта","документ","данные","можно",
         "нужно","число","страниц","ответа","счёта","счета"}


def _values(text: str) -> set[str]:
    return {
        re.sub(r"[ \u00a0]","",match.group(0)).replace(",",".")
        for match in _NUMBERS.finditer(text)
    }


def _terms(text: str) -> set[str]:
    return {
        word.casefold() for word in _WORDS.findall(text)
        if word.casefold() not in _IGNORE
    }


def check_numeric_support(
    answer: str,
    *,
    rag_items: list[dict] | None = None,
    document_fragments: list[dict] | None = None,
    verified_claims: list[dict] | None = None,
) -> dict:
    snippets=[]
    for item in (rag_items or [])[:20]:
        if item.get("source_type") not in {"document","knowledge","memory"}:
            continue
        content=str(item.get("content") or "")[:4000]
        if content.strip():
            snippets.append(content)
    for item in (document_fragments or [])[:30]:
        content=str(item.get("content") or "")[:3500]
        if content.strip():
            snippets.append(content)
    for item in (verified_claims or [])[:10]:
        if item.get("status")!="verified":
            continue
        text=str(item.get("statement") or "")[:1500]
        if text.strip():
            snippets.append(text)
    if not snippets:
        return {
            "status":"not_applicable","claims_seen":0,
            "matching_source":0,"missing_source":0,
            "warnings":[],"semantic_fact_verification":False,
        }

    indexed=[(_values(text),_terms(text)) for text in snippets]
    claims=0
    matching=0
    warnings=[]
    for sentence in _SENTENCES.split(str(answer or "")[:10000]):
        sentence=sentence.strip()
        if len(sentence)<14:
            continue
        # A numbered markdown list marker is formatting, not a claim.
        sentence=re.sub(r"^\s*(?:[-*]\s*)?\d+[.)]\s+","",sentence)
        numbers=_values(sentence)
        if not numbers:continue
        claims+=1
        terms=_terms(sentence)
        found=any(
            numbers.issubset(number_values) and
            bool(terms & source_terms)
            for number_values,source_terms in indexed
        )
        if found:
            matching+=1
        elif len(warnings)<5:
            warnings.append({
                "excerpt":sentence[:240],
                "numbers":sorted(numbers)[:12],
                "reason":"Числовые значения не найдены вместе с контекстом в доступных источниках.",
            })
        if claims>=24:break
    return {
        "status":"checked_numbers" if claims else "no_numeric_claims",
        "claims_seen":claims,
        "matching_source":matching,
        "missing_source":claims-matching,
        "warnings":warnings,
        "semantic_fact_verification":False,
        "note":"Совпадение чисел — только ориентир. Смысл и истинность вывода не доказаны.",
    }
