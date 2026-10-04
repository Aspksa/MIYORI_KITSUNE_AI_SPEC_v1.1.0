"""Conservative, project-scoped historical conversation recall.

Past chat messages are *quoted evidence of what was said*, not verified facts,
permissions, profile truth, or tool instructions. The current message alone
determines whether lookup is appropriate. No indexing or extra LLM call.
"""
from __future__ import annotations

import re
from .db import connect

_RECALL = re.compile(
    r"(?i)\b(в прошл(ом|ый)|ранее|раньше|вчера|позавчера|"
    r"в другом чате|в стар(ом|ых) чат|помнишь|помните|"
    r"мы обсуждали|мы решили|мы договорились|что я говорил|"
    r"что я писал|напомни|когда мы говорили|история разговор|"
    r"о ч[её]м говорили|что мы обсуждали)\b"
)
_WORDS = re.compile(r"[\wа-яё]{3,}", re.IGNORECASE)
_STOP = {
    "что","где","как","когда","мне","меня","было","раньше","говорили",
    "говорил","помнишь","помните","обсуждали","напомни","разговор",
    "прошлом","вчера","позавчера","другом","чате","старом","старых",
    "история","проекте","этого","проект","сейчас","такое","пожалуйста",
    "нужно","можно","скажи","последний","последний","раз","мой","моя",
    "мои","про","нами","тебе","тебя","мной","почему","только","еще",
}


def wants_history(message: str) -> bool:
    return bool(_RECALL.search(str(message or "")[:1800]))


def relevant_history(
    project_id: int,
    current_message: str,
    *,
    active_conversation_id: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Retrieve only textual snippets from the same project, capped and ranked.

    The caller must never feed these excerpts to an action/permission planner.
    """
    if not wants_history(current_message):
        return []
    tokens = list(dict.fromkeys(
        term.lower() for term in _WORDS.findall(current_message[:1800])
        if term.lower() not in _STOP and len(term) >= 4
    ))[:7]
    max_rows = 400
    with connect() as db:
        # A bounded SQL lookup with literal LIKE parameters, never user SQL.
        # Include only actual dialog roles, not tool logs or metadata.
        condition = ""
        params: list[object] = [int(project_id)]
        if tokens:
            terms = []
            for token in tokens:
                escaped = (token.replace("!", "!!")
                                .replace("%", "!%").replace("_", "!_"))
                terms.append("m.content LIKE ? ESCAPE '!'")
                params.append("%" + escaped + "%")
            condition = " AND (" + " OR ".join(terms) + ")"
        rows = db.execute(
            "SELECT m.id, m.conversation_id, m.role, m.content, "
            "m.created_at, c.title "
            "FROM messages m JOIN conversations c ON c.id=m.conversation_id "
            "WHERE c.project_id=? AND m.role IN ('user','assistant') "
            + condition + " ORDER BY m.id DESC LIMIT ?",
            [*params,max_rows],
        ).fetchall()

    ranked: list[tuple[int,int,dict]] = []
    for row in rows:
        data = dict(row)
        content = str(data["content"] or "")
        if not content.strip():
            continue
        # Exclude the current prompt and a small context window already
        # present in recent_messages() to avoid misleading repetitions.
        if (active_conversation_id is not None and
                data["conversation_id"] == active_conversation_id and
                content.strip().casefold() == current_message.strip().casefold()):
            continue
        overlap = sum(1 for token in tokens if token in content.casefold())
        if tokens and not overlap:
            continue
        score = overlap * 10
        if active_conversation_id == data["conversation_id"]:
            score += 1
        ranked.append((score,int(data["id"]),data))
    ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)
    selected=[]
    used_conversations: dict[int,int]={}
    for _,_,data in ranked:
        cid=int(data["conversation_id"])
        if used_conversations.get(cid,0)>=3:
            continue
        used_conversations[cid]=used_conversations.get(cid,0)+1
        selected.append({
            "message_id":int(data["id"]),
            "conversation_id":cid,
            "title":str(data["title"] or "Разговор")[:100],
            "role":data["role"],
            "text":str(data["content"])[:850],
            "created_at":data["created_at"],
            "source_type":"previous_chat_unverified",
        })
        if len(selected)>=max(1,min(limit,6)):
            break
    return selected
