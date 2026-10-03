from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .db import connect, utc_now

CLAIM_STATUSES = {"candidate", "supported", "verified", "disputed", "rejected", "superseded"}
CLAIM_TYPES = {"fact", "preference", "hypothesis", "strategy"}
SOURCE_TYPES = {"user_message", "document", "tool", "external", "manual"}
STANCES = {"supports", "contradicts", "neutral"}


@dataclass(frozen=True)
class VerificationResult:
    claim_id: int
    status: str
    confidence: float
    support_score: float
    contradiction_score: float
    independent_supports: int
    independent_contradictions: int
    reason: str


def init_epistemic_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS epistemic_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_type TEXT NOT NULL CHECK(source_type IN ('user_message','document','tool','external','manual')),
                source_key TEXT,
                title TEXT,
                locator TEXT,
                publisher TEXT,
                quality REAL NOT NULL DEFAULT 0.5,
                independent_group TEXT,
                metadata_json TEXT,
                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS epistemic_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                claim_type TEXT NOT NULL CHECK(claim_type IN ('fact','preference','hypothesis','strategy')),
                status TEXT NOT NULL CHECK(status IN ('candidate','supported','verified','disputed','rejected','superseded')),
                confidence REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                verified_at TEXT,
                supersedes_claim_id INTEGER,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(supersedes_claim_id) REFERENCES epistemic_claims(id)
            );

            CREATE TABLE IF NOT EXISTS epistemic_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                stance TEXT NOT NULL CHECK(stance IN ('supports','contradicts','neutral')),
                excerpt TEXT,
                weight REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                UNIQUE(claim_id, source_id, stance),
                FOREIGN KEY(claim_id) REFERENCES epistemic_claims(id) ON DELETE CASCADE,
                FOREIGN KEY(source_id) REFERENCES epistemic_sources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS epistemic_contradictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                left_claim_id INTEGER NOT NULL,
                right_claim_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open','resolved','dismissed')),
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(left_claim_id, right_claim_id),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(left_claim_id) REFERENCES epistemic_claims(id) ON DELETE CASCADE,
                FOREIGN KEY(right_claim_id) REFERENCES epistemic_claims(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_epistemic_claims_project_status
            ON epistemic_claims(project_id, status);

            CREATE INDEX IF NOT EXISTS idx_epistemic_evidence_claim
            ON epistemic_evidence(claim_id);

            CREATE INDEX IF NOT EXISTS idx_epistemic_sources_project
            ON epistemic_sources(project_id);
            """
        )


def _clean_statement(statement: str) -> str:
    clean = " ".join(statement.strip().split())
    if not clean:
        raise ValueError("Утверждение пустое.")
    if len(clean) > 1000:
        raise ValueError("Утверждение длиннее 1000 символов.")
    return clean


def _tokens(text: str) -> set[str]:
    stop = {
        "что", "это", "как", "для", "или", "при", "под", "над", "без", "есть",
        "был", "была", "будет", "мне", "мой", "моя", "мои", "твой", "твоя",
        "так", "уже", "ещё", "очень", "можно", "нужно", "надо", "если",
    }
    return {
        token for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}", text.lower())
        if token not in stop
    }


def claim_assessment(
    status: str,
    confidence: float | None = None,
    open_contradictions: int = 0,
) -> str:
    if int(open_contradictions or 0) > 0 or status == "disputed":
        return "Есть противоречия"
    if status == "verified":
        return "Подтверждено"
    if status == "supported":
        return "Вероятно"
    if status == "rejected":
        return "Опровергнуто"
    if status == "superseded":
        return "Устарело"
    return "Недостаточно данных"


def infer_claim_type(statement: str) -> str:
    text = statement.lower()
    if any(marker in text for marker in ("мне нравится", "я предпочитаю", "хочу чтобы", "мне удобнее", "я люблю когда")):
        return "preference"
    if any(marker in text for marker in ("возможно", "предполож", "может быть", "вероятно")):
        return "hypothesis"
    if any(marker in text for marker in ("лучше сначала", "стратегия", "подход", "эффективнее")):
        return "strategy"
    return "fact"


def create_source(
    project_id: int,
    source_type: str,
    *,
    source_key: str | None = None,
    title: str | None = None,
    locator: str | None = None,
    publisher: str | None = None,
    quality: float = 0.5,
    independent_group: str | None = None,
    metadata: dict | None = None,
) -> dict:
    if source_type not in SOURCE_TYPES:
        raise ValueError("Недопустимый тип источника.")
    quality = max(0.0, min(1.0, float(quality)))
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO epistemic_sources(
                project_id, source_type, source_key, title, locator, publisher,
                quality, independent_group, metadata_json, observed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, source_type, source_key, title, locator, publisher,
                quality, independent_group, json.dumps(metadata or {}, ensure_ascii=False),
                utc_now(), utc_now(),
            ),
        )
        row = conn.execute("SELECT * FROM epistemic_sources WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def create_claim(
    project_id: int,
    statement: str,
    *,
    claim_type: str | None = None,
    status: str = "candidate",
    confidence: float = 0.0,
    supersedes_claim_id: int | None = None,
) -> dict:
    clean = _clean_statement(statement)
    claim_type = claim_type or infer_claim_type(clean)
    if claim_type not in CLAIM_TYPES:
        raise ValueError("Недопустимый тип утверждения.")
    if status not in CLAIM_STATUSES:
        raise ValueError("Недопустимый статус утверждения.")
    confidence = max(0.0, min(1.0, float(confidence)))

    with connect() as conn:
        duplicate = conn.execute(
            """
            SELECT * FROM epistemic_claims
            WHERE project_id = ? AND lower(statement) = lower(?) AND status != 'superseded'
            ORDER BY id DESC LIMIT 1
            """,
            (project_id, clean),
        ).fetchone()
        if duplicate:
            return dict(duplicate)

        now = utc_now()
        cur = conn.execute(
            """
            INSERT INTO epistemic_claims(
                project_id, statement, claim_type, status, confidence,
                created_at, updated_at, verified_at, supersedes_claim_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, clean, claim_type, status, confidence,
                now, now, now if status == "verified" else None, supersedes_claim_id,
            ),
        )
        row = conn.execute("SELECT * FROM epistemic_claims WHERE id = ?", (cur.lastrowid,)).fetchone()
    claim = dict(row)
    detect_contradictions(project_id, int(claim["id"]))
    return claim


def add_evidence(
    project_id: int,
    claim_id: int,
    source_id: int,
    stance: str,
    *,
    excerpt: str | None = None,
    weight: float = 1.0,
) -> dict:
    if stance not in STANCES:
        raise ValueError("Недопустимая позиция доказательства.")
    excerpt = (excerpt or "").strip()[:2000] or None
    weight = max(0.0, min(2.0, float(weight)))
    with connect() as conn:
        claim = conn.execute(
            "SELECT id FROM epistemic_claims WHERE id = ? AND project_id = ?",
            (claim_id, project_id),
        ).fetchone()
        source = conn.execute(
            "SELECT id FROM epistemic_sources WHERE id = ? AND project_id = ?",
            (source_id, project_id),
        ).fetchone()
        if not claim or not source:
            raise ValueError("Утверждение или источник не найден в проекте.")
        conn.execute(
            """
            INSERT INTO epistemic_evidence(claim_id, source_id, stance, excerpt, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(claim_id, source_id, stance)
            DO UPDATE SET excerpt = excluded.excerpt, weight = excluded.weight
            """,
            (claim_id, source_id, stance, excerpt, weight, utc_now()),
        )
        row = conn.execute(
            """
            SELECT e.*, s.source_type, s.title AS source_title, s.quality, s.independent_group
            FROM epistemic_evidence e
            JOIN epistemic_sources s ON s.id = e.source_id
            WHERE e.claim_id = ? AND e.source_id = ? AND e.stance = ?
            """,
            (claim_id, source_id, stance),
        ).fetchone()
    verify_claim(project_id, claim_id)
    return dict(row)


def _evidence_rows(project_id: int, claim_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                e.id, e.stance, e.excerpt, e.weight,
                s.id AS source_id, s.source_type, s.source_key, s.title AS source_title,
                s.locator, s.publisher, s.quality, s.independent_group, s.observed_at
            FROM epistemic_evidence e
            JOIN epistemic_sources s ON s.id = e.source_id
            JOIN epistemic_claims c ON c.id = e.claim_id
            WHERE c.project_id = ? AND e.claim_id = ?
            ORDER BY e.id ASC
            """,
            (project_id, claim_id),
        ).fetchall()
    return [dict(row) for row in rows]


def verify_claim(project_id: int, claim_id: int) -> VerificationResult:
    with connect() as conn:
        claim_row = conn.execute(
            "SELECT * FROM epistemic_claims WHERE id = ? AND project_id = ?",
            (claim_id, project_id),
        ).fetchone()
    if not claim_row:
        raise ValueError("Утверждение не найдено.")
    claim = dict(claim_row)
    evidence = _evidence_rows(project_id, claim_id)

    support_score = 0.0
    contradiction_score = 0.0
    support_groups: set[str] = set()
    contradiction_groups: set[str] = set()

    for item in evidence:
        group = item.get("independent_group") or f"source:{item['source_id']}"
        score = float(item["quality"]) * float(item["weight"])
        if item["stance"] == "supports":
            support_score += score
            support_groups.add(group)
        elif item["stance"] == "contradicts":
            contradiction_score += score
            contradiction_groups.add(group)

    direct_user_support = any(
        item["source_type"] == "user_message" and item["stance"] == "supports"
        for item in evidence
    )

    if claim["claim_type"] == "preference" and direct_user_support and contradiction_score < 0.5:
        status = "verified"
        confidence = 1.0
        reason = "Личное предпочтение подтверждено прямым сообщением пользователя."
    elif contradiction_score >= 0.8 and support_score >= 0.8:
        status = "disputed"
        confidence = min(0.95, max(support_score, contradiction_score) / max(1.0, support_score + contradiction_score))
        reason = "Есть существенные подтверждающие и противоречащие свидетельства."
    elif contradiction_score >= 1.2 and contradiction_score > support_score * 1.25:
        status = "rejected"
        confidence = min(0.95, contradiction_score / max(1.0, contradiction_score + support_score))
        reason = "Противоречащие свидетельства существенно сильнее подтверждающих."
    elif len(support_groups) >= 2 and support_score >= 1.4 and contradiction_score < 0.6:
        status = "verified"
        confidence = min(0.98, 0.65 + support_score * 0.12)
        reason = "Утверждение поддержано несколькими независимыми источниками."
    elif support_score >= 0.6 and support_score > contradiction_score:
        status = "supported"
        confidence = min(0.85, 0.45 + support_score * 0.2)
        reason = "Есть подтверждающие свидетельства, но порог независимой проверки ещё не достигнут."
    else:
        status = "candidate"
        confidence = min(0.49, support_score * 0.25)
        reason = "Доказательств пока недостаточно."

    with connect() as conn:
        conn.execute(
            """
            UPDATE epistemic_claims
            SET status = ?, confidence = ?, updated_at = ?,
                verified_at = CASE WHEN ? = 'verified' THEN COALESCE(verified_at, ?) ELSE verified_at END
            WHERE id = ? AND project_id = ?
            """,
            (status, confidence, utc_now(), status, utc_now(), claim_id, project_id),
        )

    return VerificationResult(
        claim_id=claim_id,
        status=status,
        confidence=round(confidence, 4),
        support_score=round(support_score, 4),
        contradiction_score=round(contradiction_score, 4),
        independent_supports=len(support_groups),
        independent_contradictions=len(contradiction_groups),
        reason=reason,
    )


def detect_contradictions(project_id: int, claim_id: int) -> list[dict]:
    with connect() as conn:
        current = conn.execute(
            "SELECT id, statement, claim_type FROM epistemic_claims WHERE id = ? AND project_id = ?",
            (claim_id, project_id),
        ).fetchone()
        if not current:
            return []
        rows = conn.execute(
            """
            SELECT id, statement, claim_type
            FROM epistemic_claims
            WHERE project_id = ? AND id != ?
              AND status IN ('candidate','supported','verified','disputed')
            ORDER BY id DESC LIMIT 300
            """,
            (project_id, claim_id),
        ).fetchall()

    current_tokens = _tokens(current["statement"])
    if len(current_tokens) < 2:
        return []

    negation_markers = {"не", "нет", "никогда", "нельзя", "отсутствует", "без"}
    current_words = set(re.findall(r"[а-яёa-z0-9_-]+", current["statement"].lower()))
    found = []

    for row in rows:
        other_tokens = _tokens(row["statement"])
        shared = current_tokens & other_tokens
        if len(shared) < 2:
            continue
        other_words = set(re.findall(r"[а-яёa-z0-9_-]+", row["statement"].lower()))
        negation_differs = bool(current_words & negation_markers) != bool(other_words & negation_markers)
        current_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", current["statement"]))
        other_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", row["statement"]))
        numeric_conflict = (
            len(shared) >= 3
            and bool(current_numbers)
            and bool(other_numbers)
            and current_numbers != other_numbers
            and current["claim_type"] == row["claim_type"]
        )
        if not negation_differs and not numeric_conflict:
            continue

        left, right = sorted((claim_id, int(row["id"])))
        reason = (
            "Похожие утверждения содержат разные числовые значения; требуется сверка источников."
            if numeric_conflict and not negation_differs
            else "Похожие утверждения содержат различающуюся отрицательную формулировку; требуется проверка."
        )
        with connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO epistemic_contradictions(
                    project_id, left_claim_id, right_claim_id, reason, status, created_at
                ) VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (project_id, left, right, reason, utc_now()),
            )
            rec = conn.execute(
                """
                SELECT * FROM epistemic_contradictions
                WHERE project_id = ? AND left_claim_id = ? AND right_claim_id = ?
                """,
                (project_id, left, right),
            ).fetchone()
        if rec:
            found.append(dict(rec))
    return found


def list_claims(project_id: int, status: str | None = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 300))
    params: list[object] = [project_id]
    where = "WHERE c.project_id = ?"
    if status:
        if status not in CLAIM_STATUSES:
            raise ValueError("Недопустимый статус.")
        where += " AND c.status = ?"
        params.append(status)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT c.*,
                SUM(CASE WHEN e.stance = 'supports' THEN 1 ELSE 0 END) AS supports,
                SUM(CASE WHEN e.stance = 'contradicts' THEN 1 ELSE 0 END) AS contradictions,
                (
                    SELECT COUNT(*)
                    FROM epistemic_contradictions x
                    WHERE x.project_id = c.project_id AND x.status = 'open'
                      AND (x.left_claim_id = c.id OR x.right_claim_id = c.id)
                ) AS open_contradictions
            FROM epistemic_claims c
            LEFT JOIN epistemic_evidence e ON e.claim_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["assessment"] = claim_assessment(
            item["status"],
            item.get("confidence"),
            item.get("open_contradictions", 0),
        )
        result.append(item)
    return result


def get_claim(project_id: int, claim_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM epistemic_claims WHERE id = ? AND project_id = ?",
            (claim_id, project_id),
        ).fetchone()
        if not row:
            return None
        contradictions = conn.execute(
            """
            SELECT * FROM epistemic_contradictions
            WHERE project_id = ? AND (left_claim_id = ? OR right_claim_id = ?)
            ORDER BY id DESC
            """,
            (project_id, claim_id, claim_id),
        ).fetchall()
    result = dict(row)
    result["evidence"] = _evidence_rows(project_id, claim_id)
    result["contradictions"] = [dict(item) for item in contradictions]
    result["assessment"] = claim_assessment(
        result["status"],
        result.get("confidence"),
        sum(1 for item in contradictions if item["status"] == "open"),
    )
    return result


def epistemic_snapshot(project_id: int) -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM epistemic_claims WHERE project_id = ?
            GROUP BY status
            """,
            (project_id,),
        ).fetchall()
        open_contradictions = conn.execute(
            "SELECT COUNT(*) AS count FROM epistemic_contradictions WHERE project_id = ? AND status = 'open'",
            (project_id,),
        ).fetchone()["count"]
        sources = conn.execute(
            "SELECT COUNT(*) AS count FROM epistemic_sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
    counts = {status: 0 for status in CLAIM_STATUSES}
    counts.update({row["status"]: int(row["count"]) for row in rows})
    return {
        "claims": counts,
        "sources": int(sources),
        "open_contradictions": int(open_contradictions),
        "assessment": {
            "Подтверждено": counts.get("verified", 0),
            "Вероятно": counts.get("supported", 0),
            "Есть противоречия": int(open_contradictions),
            "Недостаточно данных": counts.get("candidate", 0),
        },
    }


def trusted_claim_context(project_id: int, query: str, limit: int = 6) -> list[dict]:
    query_tokens = _tokens(query)
    candidates = list_claims(project_id, limit=200)
    scored: list[tuple[float, dict]] = []
    for claim in candidates:
        if claim["status"] not in {"verified", "supported"}:
            continue
        overlap = len(query_tokens & _tokens(claim["statement"]))
        if not overlap and query_tokens:
            continue
        status_bonus = 2.0 if claim["status"] == "verified" else 1.0
        score = overlap * 10 + status_bonus + float(claim["confidence"])
        scored.append((score, claim))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [claim for _, claim in scored[:limit]]


def capture_user_claims(
    project_id: int,
    conversation_id: int,
    message_id: int,
    text: str,
) -> list[dict]:
    clean_text = text.strip()
    if not clean_text or len(clean_text) > 5000:
        return []

    source = create_source(
        project_id,
        "user_message",
        source_key=f"message:{message_id}",
        title=f"Сообщение пользователя #{message_id}",
        locator=f"conversation:{conversation_id}/message:{message_id}",
        quality=1.0,
        independent_group=f"user:{message_id}",
    )

    created: list[dict] = []
    sentences = re.split(r"(?<=[.!])\s+|\n+", clean_text)
    command_starts = (
        "сделай ", "создай ", "проверь ", "найди ", "покажи ", "расскажи ",
        "давай ", "нужно ", "хочу чтобы ты ", "можешь ",
    )

    for sentence in sentences[:8]:
        sentence = sentence.strip(" -\t")
        if not sentence or sentence.endswith("?") or len(sentence) < 8:
            continue
        lower = sentence.lower()
        if lower.startswith(command_starts):
            continue

        claim_type = infer_claim_type(sentence)
        if claim_type == "fact" and len(_tokens(sentence)) < 3:
            continue

        claim = create_claim(project_id, sentence[:1000], claim_type=claim_type)
        add_evidence(
            project_id,
            int(claim["id"]),
            int(source["id"]),
            "supports",
            excerpt=sentence,
            weight=1.0 if claim_type == "preference" else 0.55,
        )
        refreshed = get_claim(project_id, int(claim["id"]))
        if refreshed:
            created.append(refreshed)
    return created
