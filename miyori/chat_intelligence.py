"""Conservative, deterministic chat context planning.

Only the *current* user's text authorizes tools; history may help retrieval
but must never authorize actions, permissions or cross-project access.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .context_router import ContextRoute, route_context

_FOLLOWUP = re.compile(
    r"^(а |и |ну |тогда |ещ[её] |что насч[её]т |какой |какая |какие |"
    r"сколько |почему |когда |где |это |этот |эти |там |по нему|по ней|"
    r"сравни их|проверь их|теперь )",
    re.IGNORECASE,
)
_REFERENCE = re.compile(
    r"\b(этот|этом|этим|этих|того|том|его|её|их|указанн|"
    r"выше|раньше|предыдущ|продолж|второй|первый)\w*\b",
    re.IGNORECASE,
)
_ANALYSIS = (
    "сравни","сверь","расхожд","противореч","проверь","проверка",
    "проанализируй","найди ошиб","сопоставь","рассчитай",
)
_DEEP = ("подробно","полностью","все страницы","глубокий","по пунктам","все документы")


@dataclass(frozen=True)
class ChatQueryPlan:
    retrieval_query: str
    depth: str
    is_followup: bool
    attached_count: int
    reasons: tuple[str, ...]

    def public_summary(self) -> dict:
        return {
            "mode": self.depth,
            "followup": self.is_followup,
            "documents": self.attached_count,
            "reasons": list(self.reasons),
        }


def plan_chat_query(
    message: str,
    history: list[dict[str,str]] | None,
    attached_count: int = 0,
) -> ChatQueryPlan:
    current = " ".join(message.strip().split())[:900]
    previous_user = ""
    # recent_messages includes the just-persisted user prompt. Exclude it.
    skipped_current = False
    for row in reversed((history or [])[-20:]):
        if row.get("role") != "user":
            continue
        content = " ".join(str(row.get("content") or "").split())
        if not skipped_current and content == current:
            skipped_current = True
            continue
        previous_user = content[:400]
        break

    followup = bool(previous_user) and (
        bool(_REFERENCE.search(current))
        or (len(current) <= 110 and bool(_FOLLOWUP.search(current)))
    )
    reasons = []
    retrieval = current
    if followup:
        # Context is data for retrieval, never an instruction for tools.
        retrieval = (previous_user + " ; Уточнение: " + current)[:950]
        reasons.append("followup_context_for_retrieval")

    lower = current.lower()
    comparison = sum(marker in lower for marker in _ANALYSIS)
    explicit_depth = any(marker in lower for marker in _DEEP)
    if attached_count > 1 and comparison or explicit_depth or comparison >= 2:
        depth = "deep"
    elif attached_count or comparison or len(current) > 240:
        depth = "standard"
    else:
        depth = "fast"
    reasons.append("complex_request" if depth == "deep" else "minimal_route" if depth == "fast" else "regular_request")
    if attached_count:
        reasons.append("explicit_attachments")
    return ChatQueryPlan(
        retrieval_query=retrieval,
        depth=depth,
        is_followup=followup,
        attached_count=max(0,attached_count),
        reasons=tuple(reasons),
    )


def enhance_context_route(
    current_message: str,
    plan: ChatQueryPlan,
    *,
    forced_read_only: bool = False,
) -> ContextRoute:
    """History improves retrieval, not the authority to act."""
    from dataclasses import replace

    route = route_context(current_message)
    notes = list(route.reasons)
    if plan.is_followup:
        previous = route_context(plan.retrieval_query)
        lower = current_message.lower()
        no_documents = any(marker in lower for marker in (
            "без документов","не ищи в документах","не используй документы",
        ))
        no_memory = "без памяти" in lower or "не используй память" in lower
        route = replace(
            route,
            use_documents=route.use_documents or (previous.use_documents and not no_documents),
            use_user_memory=route.use_user_memory or (previous.use_user_memory and not no_memory),
            use_project_memory=route.use_project_memory or (
                previous.use_project_memory and not no_memory
            ),
            use_epistemic=route.use_epistemic or previous.use_epistemic,
            # CRITICAL: do not inherit use_tools from previous user messages.
            use_tools=route.use_tools,
        )
        notes.append("followup_retrieval_only")
    if plan.attached_count and not route.use_documents:
        # Explicit user attachments are selected sources for this turn.
        route = replace(route,use_documents=True)
        notes.append("explicit_attachments")
    if forced_read_only and route.use_tools:
        route=replace(route,use_tools=False)
        notes.append("read_only_fork_no_tools")
    if plan.depth=="deep" and route.use_documents:
        route=replace(route,max_rag_items=max(route.max_rag_items,12))
    return replace(route,reasons=tuple(dict.fromkeys([*notes,*route.reasons])))
