from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re


@dataclass(frozen=True)
class ContextRoute:
    use_recent_messages: bool = True
    use_user_memory: bool = False
    use_project_memory: bool = False
    use_documents: bool = False
    use_epistemic: bool = False
    use_tools: bool = False
    max_rag_items: int = 8
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)


_DOCUMENT_MARKERS = (
    "документ", "файл", "папк", "договор", "контракт", "счёт", "счет",
    "накладн", "акт ", "pdf", "docx", "xlsx", "pptx", "таблиц", "приложен",
    "спецификац", "инструкц", "регламент", "по материал", "в документ",
)
_MEMORY_MARKERS = (
    "помни", "памят", "я говорил", "я писал", "я предпочитаю", "мне нравится",
    "мне не нравится", "мой ", "моя ", "мои ", "обычно я", "для меня",
)
_PROJECT_MEMORY_MARKERS = (
    "в этом проект", "для проекта", "по проекту", "наша компания", "наш процесс",
    "контрагент", "сотрудник", "правило проекта", "рабочий процесс",
)
_EPISTEMIC_MARKERS = (
    "проверь", "верно ли", "правда ли", "подтверди", "источник", "доказ",
    "противореч", "расхожд", "точно ли", "насколько уверен", "сомнен",
)
_ACTION_MARKERS = (
    "создай", "сделай папк", "перемести", "положи", "удали", "восстанов",
    "запиши", "сохрани", "измени файл", "создай файл", "обнови файл",
)
_PROJECT_STATUS_MARKERS = (
    "статус проекта", "состояние проекта", "проверь проект", "готов ли проект",
)
_NO_DOCUMENT_MARKERS = (
    "без документов", "не ищи в документах", "не используй документы",
)
_NO_MEMORY_MARKERS = (
    "без памяти", "не используй память",
)


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def route_context(message: str) -> ContextRoute:
    text = " ".join(message.strip().split())
    lower = text.lower()

    document_signal = _contains(lower, _DOCUMENT_MARKERS)
    memory_signal = _contains(lower, _MEMORY_MARKERS)
    project_memory_signal = _contains(lower, _PROJECT_MEMORY_MARKERS)
    epistemic_signal = _contains(lower, _EPISTEMIC_MARKERS)
    action_signal = _contains(lower, _ACTION_MARKERS)
    status_signal = _contains(lower, _PROJECT_STATUS_MARKERS)

    # Requests to find/analyse concrete project material should search documents
    # even when the word "document" is omitted.
    lookup_signal = bool(re.search(
        r"\b(найди|отыщи|покажи|сравни|проанализируй|сверь|проверь)\b",
        lower,
    ))
    business_object_signal = bool(re.search(
        r"\b(договор|контрагент|сч[её]т|сотрудник|акт|накладн|спецификац)\w*",
        lower,
    ))
    if lookup_signal and business_object_signal:
        document_signal = True

    reasons: list[str] = []
    use_documents = document_signal
    use_user_memory = memory_signal
    use_project_memory = project_memory_signal or document_signal
    use_epistemic = epistemic_signal or (
        document_signal and any(word in lower for word in ("сравни", "сверь", "проверь"))
    )
    use_tools = action_signal or status_signal or (
        lookup_signal and (document_signal or memory_signal or project_memory_signal)
    )

    if _contains(lower, _NO_DOCUMENT_MARKERS):
        use_documents = False
        reasons.append("documents_explicitly_disabled")
    elif use_documents:
        reasons.append("project_documents_relevant")

    if _contains(lower, _NO_MEMORY_MARKERS):
        use_user_memory = False
        use_project_memory = False
        reasons.append("memory_explicitly_disabled")
    else:
        if use_user_memory:
            reasons.append("user_memory_relevant")
        if use_project_memory:
            reasons.append("project_memory_relevant")

    if use_epistemic:
        reasons.append("verification_or_conflict_check")
    if use_tools:
        reasons.append("tool_or_action_intent")

    if not reasons:
        reasons.append("recent_conversation_only")

    max_items = 10 if use_documents and use_epistemic else 8 if use_documents else 6

    return ContextRoute(
        use_recent_messages=True,
        use_user_memory=use_user_memory,
        use_project_memory=use_project_memory,
        use_documents=use_documents,
        use_epistemic=use_epistemic,
        use_tools=use_tools,
        max_rag_items=max_items,
        reasons=tuple(reasons),
    )
