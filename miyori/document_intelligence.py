from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .config import settings
from .db import (
    connect,
    create_task,
    get_document,
    is_task_cancel_requested,
    record_task_event,
    utc_now,
)
from .documents import (
    StructuredDocument,
    extract_structured_document,
    resolve_data_path,
)
from .provider import (
    ProviderError,
    analyze_document_window,
    synthesize_document_analysis,
)

PARSER_VERSION = "1.0.0"
ANALYSIS_WINDOW_CHARS = 18_000
SYNTHESIS_INPUT_CHARS = 24_000

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}")
_STOPWORDS = {
    "что", "это", "как", "для", "или", "при", "под", "над", "без", "есть",
    "был", "была", "будет", "мне", "мой", "моя", "мои", "так", "уже",
    "ещё", "очень", "можно", "нужно", "если", "когда", "где", "чем",
    "который", "которая", "которые", "также", "его", "ее", "её", "их",
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
}


def init_document_intelligence_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_intelligence (
                document_id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'indexed'
                    CHECK(status IN (
                        'indexed','queued','analyzing','complete','partial',
                        'needs_ocr','unsupported','failed'
                    )),
                parser_version TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                title TEXT,
                document_kind TEXT NOT NULL,
                language TEXT,
                char_count INTEGER NOT NULL DEFAULT 0,
                word_count INTEGER NOT NULL DEFAULT 0,
                page_count INTEGER NOT NULL DEFAULT 0,
                section_count INTEGER NOT NULL DEFAULT 0,
                table_count INTEGER NOT NULL DEFAULT 0,
                node_count INTEGER NOT NULL DEFAULT 0,
                analyzed_chars INTEGER NOT NULL DEFAULT 0,
                coverage_ratio REAL NOT NULL DEFAULT 0.0,
                summary_short TEXT,
                summary_long TEXT,
                outline_json TEXT NOT NULL DEFAULT '[]',
                keywords_json TEXT NOT NULL DEFAULT '[]',
                analysis_json TEXT NOT NULL DEFAULT '{}',
                analysis_model TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS document_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                parent_node_id INTEGER,
                node_index INTEGER NOT NULL,
                node_type TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 0,
                title TEXT,
                locator TEXT NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                word_count INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                local_summary TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(document_id, node_index),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY(parent_node_id) REFERENCES document_nodes(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS document_analysis_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                window_index INTEGER NOT NULL,
                start_node_index INTEGER NOT NULL,
                end_node_index INTEGER NOT NULL,
                source_chars INTEGER NOT NULL,
                source_fingerprint TEXT NOT NULL DEFAULT '',
                locator_start TEXT,
                locator_end TEXT,
                summary TEXT,
                analysis_json TEXT NOT NULL DEFAULT '{}',
                model_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(document_id, window_index),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_document_intelligence_project
                ON document_intelligence(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_document_nodes_document
                ON document_nodes(document_id, node_index);
            CREATE INDEX IF NOT EXISTS idx_document_nodes_project
                ON document_nodes(project_id, document_id);
            CREATE INDEX IF NOT EXISTS idx_document_windows_document
                ON document_analysis_windows(document_id, window_index);
            """
        )
        window_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(document_analysis_windows)"
            ).fetchall()
        }
        if "source_fingerprint" not in window_columns:
            conn.execute(
                """
                ALTER TABLE document_analysis_windows
                ADD COLUMN source_fingerprint TEXT NOT NULL DEFAULT ''
                """
            )


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(str(text or "").lower())
        if token not in _STOPWORDS
    ]


def _language(text: str) -> str:
    sample = str(text or "")[:80_000]
    cyr = len(re.findall(r"[а-яА-ЯёЁ]", sample))
    lat = len(re.findall(r"[a-zA-Z]", sample))
    if cyr > lat * 1.4:
        return "ru"
    if lat > cyr * 1.4:
        return "en"
    return "mixed"


def _document_kind(format_name: str) -> str:
    return {
        "xlsx": "spreadsheet",
        "pptx": "presentation",
        "json": "structured_data",
        "pdf": "document",
        "docx": "document",
        "md": "document",
        "markdown": "document",
        "txt": "document",
    }.get(format_name, "document")


def _extractive_summary(text: str, limit: int = 700) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    selected: list[str] = []
    total = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if total + len(sentence) > limit and selected:
            break
        selected.append(sentence)
        total += len(sentence) + 1
        if len(selected) >= 4:
            break
    result = " ".join(selected).strip()
    return result[:limit]


def _top_keywords(text: str, limit: int = 24) -> list[str]:
    counts = Counter(_tokens(text))
    return [token for token, _ in counts.most_common(limit)]


def _profile_row(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["outline"] = _loads(item.pop("outline_json", None), [])
    item["keywords"] = _loads(item.pop("keywords_json", None), [])
    item["analysis"] = _loads(item.pop("analysis_json", None), {})
    item["coverage_ratio"] = float(item.get("coverage_ratio") or 0.0)
    return item


def _node_row(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["metadata"] = _loads(item.pop("metadata_json", None), {})
    return item


def get_document_intelligence(project_id: int, document_id: int) -> dict | None:
    init_document_intelligence_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM document_intelligence
            WHERE document_id = ? AND project_id = ?
            """,
            (document_id, project_id),
        ).fetchone()
    return _profile_row(row)


def list_document_intelligence(project_id: int) -> list[dict]:
    init_document_intelligence_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT di.*, d.filename, d.folder_id, d.size_bytes, d.created_at AS document_created_at
            FROM document_intelligence di
            JOIN documents d ON d.id = di.document_id
            WHERE di.project_id = ? AND d.deleted_at IS NULL
            ORDER BY d.id DESC
            """,
            (project_id,),
        ).fetchall()
    return [_profile_row(row) for row in rows]


def get_document_nodes(
    project_id: int,
    document_id: int,
    *,
    offset: int = 0,
    limit: int = 200,
) -> list[dict]:
    init_document_intelligence_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM document_nodes
            WHERE project_id = ? AND document_id = ?
            ORDER BY node_index ASC
            LIMIT ? OFFSET ?
            """,
            (project_id, document_id, max(1, min(int(limit), 1000)), max(0, int(offset))),
        ).fetchall()
    return [_node_row(row) for row in rows]


def get_document_node(project_id: int, document_id: int, node_id: int) -> dict | None:
    init_document_intelligence_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM document_nodes
            WHERE id = ? AND document_id = ? AND project_id = ?
            """,
            (node_id, document_id, project_id),
        ).fetchone()
    return _node_row(row)


def _outline_item(node: dict) -> dict:
    return {
        "node_id": node["id"],
        "node_index": node["node_index"],
        "type": node["node_type"],
        "level": node["level"],
        "title": node.get("title") or _extractive_summary(node.get("text", ""), 120),
        "locator": node["locator"],
    }


def build_local_document_intelligence(
    project_id: int,
    document_id: int,
    structured: StructuredDocument | None = None,
) -> dict:
    init_document_intelligence_db()
    document = get_document(project_id, document_id)
    if not document:
        raise ValueError("Документ не найден в текущем проекте.")

    if structured is None:
        path = resolve_data_path(document["stored_path"])
        if not path.exists() or not path.is_file():
            raise ValueError("Оригинал документа отсутствует на диске.")
        structured = extract_structured_document(document["filename"], path.read_bytes())

    created_at = utc_now()
    cursor = 0
    outline: list[dict] = []
    heading_stack: list[tuple[int, int]] = []
    section_count = 0

    with connect() as conn:
        conn.execute(
            "DELETE FROM document_analysis_windows WHERE document_id = ?",
            (document_id,),
        )
        conn.execute(
            "DELETE FROM document_nodes WHERE document_id = ?",
            (document_id,),
        )

        for block in structured.blocks:
            text = str(block.text or "").strip()
            if not text:
                continue

            level = max(0, int(block.level or 0))
            parent_id = heading_stack[-1][1] if heading_stack else None

            if block.kind == "heading":
                section_count += 1
                while heading_stack and heading_stack[-1][0] >= max(1, level):
                    heading_stack.pop()
                parent_id = heading_stack[-1][1] if heading_stack else None

            start_char = cursor
            end_char = start_char + len(text)
            words = len(_tokens(text))
            cur = conn.execute(
                """
                INSERT INTO document_nodes(
                    project_id, document_id, parent_node_id, node_index,
                    node_type, level, title, locator, start_char, end_char,
                    word_count, text, local_summary, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    document_id,
                    parent_id,
                    int(block.index),
                    block.kind,
                    level,
                    block.title,
                    block.locator,
                    start_char,
                    end_char,
                    words,
                    text,
                    _extractive_summary(text, 520),
                    json.dumps(block.metadata or {}, ensure_ascii=False),
                    created_at,
                ),
            )
            node_id = int(cur.lastrowid)
            cursor = end_char + 2

            node = {
                "id": node_id,
                "node_index": int(block.index),
                "node_type": block.kind,
                "level": level,
                "title": block.title,
                "locator": block.locator,
                "text": text,
            }
            if block.kind in {"heading", "slide"} or block.title:
                outline.append(_outline_item(node))

            if block.kind == "heading":
                heading_stack.append((max(1, level), node_id))

        char_count = conn.execute(
            "SELECT COALESCE(SUM(length(text)), 0) AS n FROM document_nodes WHERE document_id = ?",
            (document_id,),
        ).fetchone()["n"]
        word_count = conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) AS n FROM document_nodes WHERE document_id = ?",
            (document_id,),
        ).fetchone()["n"]
        node_count = conn.execute(
            "SELECT COUNT(*) AS n FROM document_nodes WHERE document_id = ?",
            (document_id,),
        ).fetchone()["n"]

        local_summary = _extractive_summary(structured.text, 1100)
        now = utc_now()
        conn.execute(
            """
            INSERT INTO document_intelligence(
                document_id, project_id, status, parser_version, source_sha256,
                title, document_kind, language, char_count, word_count,
                page_count, section_count, table_count, node_count,
                analyzed_chars, coverage_ratio, summary_short, summary_long,
                outline_json, keywords_json, analysis_json, analysis_model,
                last_error, created_at, updated_at
            ) VALUES (?, ?, 'indexed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0.0,
                      ?, NULL, ?, ?, '{}', NULL, NULL, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                project_id = excluded.project_id,
                status = 'indexed',
                parser_version = excluded.parser_version,
                source_sha256 = excluded.source_sha256,
                title = excluded.title,
                document_kind = excluded.document_kind,
                language = excluded.language,
                char_count = excluded.char_count,
                word_count = excluded.word_count,
                page_count = excluded.page_count,
                section_count = excluded.section_count,
                table_count = excluded.table_count,
                node_count = excluded.node_count,
                analyzed_chars = 0,
                coverage_ratio = 0.0,
                summary_short = excluded.summary_short,
                summary_long = NULL,
                outline_json = excluded.outline_json,
                keywords_json = excluded.keywords_json,
                analysis_json = '{}',
                analysis_model = NULL,
                last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (
                document_id,
                project_id,
                PARSER_VERSION,
                document["sha256"],
                structured.title,
                _document_kind(structured.format),
                _language(structured.text),
                int(char_count),
                int(word_count),
                int(structured.metadata.get("page_count") or 0),
                int(section_count),
                int(structured.metadata.get("table_count") or 0),
                int(node_count),
                local_summary,
                json.dumps(outline, ensure_ascii=False),
                json.dumps(_top_keywords(structured.text), ensure_ascii=False),
                created_at,
                now,
            ),
        )

    return get_document_intelligence(project_id, document_id) or {}


def mark_document_intelligence_unavailable(
    project_id: int,
    document_id: int,
    *,
    status: str,
    error: str,
) -> dict:
    if status not in {"needs_ocr", "unsupported", "failed"}:
        raise ValueError("Недопустимый статус Document Intelligence.")
    init_document_intelligence_db()
    document = get_document(project_id, document_id, include_deleted=True)
    if not document:
        raise ValueError("Документ не найден.")
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO document_intelligence(
                document_id, project_id, status, parser_version, source_sha256,
                title, document_kind, language, char_count, word_count,
                page_count, section_count, table_count, node_count,
                analyzed_chars, coverage_ratio, summary_short, summary_long,
                outline_json, keywords_json, analysis_json, last_error,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'document', NULL, 0, 0, 0, 0, 0, 0,
                      0, 0.0, NULL, NULL, '[]', '[]', '{}', ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                status = excluded.status,
                parser_version = excluded.parser_version,
                source_sha256 = excluded.source_sha256,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                document_id,
                project_id,
                status,
                PARSER_VERSION,
                document["sha256"],
                Path(document["filename"]).stem,
                error[:2000],
                now,
                now,
            ),
        )
    return get_document_intelligence(project_id, document_id) or {}


def rebuild_document_intelligence(project_id: int, document_id: int) -> dict:
    document = get_document(project_id, document_id)
    if not document:
        raise ValueError("Документ не найден.")
    path = resolve_data_path(document["stored_path"])
    try:
        structured = extract_structured_document(document["filename"], path.read_bytes())
    except ValueError as exc:
        lower = str(exc).lower()
        status = "needs_ocr" if "ocr" in lower or "pdf" in lower else "unsupported"
        return mark_document_intelligence_unavailable(
            project_id,
            document_id,
            status=status,
            error=str(exc),
        )
    return build_local_document_intelligence(project_id, document_id, structured)


def search_document_nodes(
    project_id: int,
    document_id: int,
    query: str,
    *,
    limit: int = 12,
    neighbor_radius: int = 1,
) -> list[dict]:
    clean_query = " ".join(str(query or "").strip().split())
    if not clean_query:
        return []
    query_tokens = set(_tokens(clean_query))
    if not query_tokens:
        return []

    init_document_intelligence_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM document_nodes
            WHERE project_id = ? AND document_id = ?
            ORDER BY node_index ASC
            """,
            (project_id, document_id),
        ).fetchall()

    scored: list[tuple[float, dict]] = []
    phrase = clean_query.casefold()
    for row in rows:
        item = _node_row(row) or {}
        haystack = f"{item.get('title') or ''} {item.get('text') or ''}"
        node_tokens = set(_tokens(haystack))
        overlap = len(query_tokens & node_tokens)
        if not overlap and phrase not in haystack.casefold():
            continue
        title_tokens = set(_tokens(item.get("title") or ""))
        score = overlap * 10.0 + len(query_tokens & title_tokens) * 4.0
        if phrase and phrase in haystack.casefold():
            score += 15.0
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], int(pair[1]["node_index"])))
    primary = [item for _, item in scored[: max(1, min(int(limit), 40))]]
    if not primary:
        return []

    by_index = {int((_node_row(row) or {})["node_index"]): _node_row(row) for row in rows}
    selected: dict[int, dict] = {}
    primary_indexes = {int(item["node_index"]) for item in primary}
    radius = max(0, min(int(neighbor_radius), 3))
    for item in primary:
        index = int(item["node_index"])
        for candidate in range(index - radius, index + radius + 1):
            node = by_index.get(candidate)
            if node:
                copy = dict(node)
                copy["matched"] = candidate in primary_indexes
                selected[candidate] = copy

    return [selected[index] for index in sorted(selected)]


def document_context_packet(
    project_id: int,
    document_id: int,
    query: str,
    *,
    max_chars: int = 14_000,
) -> dict:
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        profile = rebuild_document_intelligence(project_id, document_id)

    matches = search_document_nodes(
        project_id,
        document_id,
        query,
        limit=10,
        neighbor_radius=1,
    )
    budget = max(1000, int(max_chars))
    used = 0
    selected: list[dict] = []
    for node in matches:
        text = str(node.get("text") or "")
        if used + len(text) > budget and selected:
            break
        copy = {
            "node_id": node["id"],
            "node_index": node["node_index"],
            "type": node["node_type"],
            "title": node.get("title"),
            "locator": node["locator"],
            "text": text[: max(0, budget - used)],
            "matched": bool(node.get("matched")),
        }
        selected.append(copy)
        used += len(copy["text"])

    return {
        "document_id": document_id,
        "title": profile.get("title"),
        "status": profile.get("status"),
        "coverage_ratio": profile.get("coverage_ratio", 0.0),
        "summary": profile.get("summary_long") or profile.get("summary_short"),
        "keywords": profile.get("keywords") or [],
        "outline": (profile.get("outline") or [])[:250],
        "matches": selected,
        "context_chars": used,
    }


def search_project_document_intelligence(
    project_id: int,
    query: str,
    *,
    limit: int = 12,
) -> list[dict]:
    profiles = list_document_intelligence(project_id)
    candidates: list[tuple[float, dict]] = []
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return []

    for profile in profiles:
        searchable = " ".join(
            [
                str(profile.get("filename") or ""),
                str(profile.get("title") or ""),
                str(profile.get("summary_long") or ""),
                str(profile.get("summary_short") or ""),
                " ".join(profile.get("keywords") or []),
                " ".join(
                    str(item.get("title") or "")
                    for item in (profile.get("outline") or [])[:500]
                ),
            ]
        )
        overlap = len(query_tokens & set(_tokens(searchable)))
        if overlap:
            candidates.append(
                (
                    overlap * 8.0,
                    {
                        "document_id": profile["document_id"],
                        "filename": profile.get("filename"),
                        "title": profile.get("title"),
                        "status": profile.get("status"),
                        "coverage_ratio": profile.get("coverage_ratio"),
                        "summary": profile.get("summary_long") or profile.get("summary_short"),
                        "locator": "document:overview",
                    },
                )
            )

        for node in search_document_nodes(
            project_id,
            int(profile["document_id"]),
            query,
            limit=4,
            neighbor_radius=0,
        ):
            if not node.get("matched"):
                continue
            node_overlap = len(query_tokens & set(_tokens(
                f"{node.get('title') or ''} {node.get('text') or ''}"
            )))
            candidates.append(
                (
                    node_overlap * 10.0 + 2.0,
                    {
                        "document_id": profile["document_id"],
                        "filename": profile.get("filename"),
                        "title": node.get("title") or profile.get("title"),
                        "status": profile.get("status"),
                        "coverage_ratio": profile.get("coverage_ratio"),
                        "summary": str(node.get("text") or "")[:2400],
                        "locator": node.get("locator"),
                        "node_id": node.get("id"),
                    },
                )
            )

    candidates.sort(key=lambda item: -item[0])
    seen: set[tuple[int, str]] = set()
    result: list[dict] = []
    for score, item in candidates:
        key = (int(item["document_id"]), str(item.get("locator") or ""))
        if key in seen:
            continue
        seen.add(key)
        item["score"] = score
        result.append(item)
        if len(result) >= max(1, min(int(limit), 40)):
            break
    return result


def _analysis_segments(nodes: list[dict]) -> list[dict]:
    segments: list[dict] = []
    for node in nodes:
        text = str(node.get("text") or "")
        if not text:
            continue
        if len(text) <= ANALYSIS_WINDOW_CHARS:
            segments.append({
                "node_index": int(node["node_index"]),
                "locator": node["locator"],
                "title": node.get("title"),
                "text": text,
                "source_chars": len(text),
            })
            continue

        part = 0
        for start in range(0, len(text), ANALYSIS_WINDOW_CHARS):
            fragment = text[start:start + ANALYSIS_WINDOW_CHARS]
            part += 1
            segments.append({
                "node_index": int(node["node_index"]),
                "locator": f"{node['locator']}:part:{part}",
                "title": node.get("title"),
                "text": fragment,
                "source_chars": len(fragment),
            })
    return segments


def _pack_windows(segments: list[dict]) -> list[dict]:
    windows: list[dict] = []
    current: list[dict] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        windows.append({
            "segments": current,
            "source_chars": sum(item["source_chars"] for item in current),
            "start_node_index": current[0]["node_index"],
            "end_node_index": current[-1]["node_index"],
            "locator_start": current[0]["locator"],
            "locator_end": current[-1]["locator"],
            "content": "\n\n".join(
                f"[{item['locator']}]"
                + (f" {item['title']}" if item.get("title") else "")
                + "\n"
                + item["text"]
                for item in current
            ),
        })
        current = []
        current_chars = 0

    for segment in segments:
        addition = len(segment["text"]) + len(segment["locator"]) + 8
        if current and current_chars + addition > ANALYSIS_WINDOW_CHARS:
            flush()
        current.append(segment)
        current_chars += addition
    flush()
    return windows


def document_window_fingerprint(window: dict) -> str:
    return hashlib.sha256(
        str(window.get("content") or "").encode("utf-8")
    ).hexdigest()


def build_document_windows(project_id: int, document_id: int) -> tuple[dict, list[dict]]:
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        profile = rebuild_document_intelligence(project_id, document_id)
    if profile.get("status") in {"needs_ocr", "unsupported"}:
        raise ValueError(
            profile.get("last_error")
            or "Документ нельзя читать полностью без извлечённого текста."
        )

    nodes = get_document_nodes(project_id, document_id, offset=0, limit=1000)
    expected = int(profile.get("node_count") or 0)
    offset = len(nodes)
    while offset < expected:
        part = get_document_nodes(
            project_id,
            document_id,
            offset=offset,
            limit=1000,
        )
        if not part:
            break
        nodes.extend(part)
        offset += len(part)

    windows = _pack_windows(_analysis_segments(nodes))
    if not windows:
        raise ValueError("В документе нет текста для полного анализа.")
    for window in windows:
        window["source_fingerprint"] = document_window_fingerprint(window)
    return profile, windows


def _save_window(
    project_id: int,
    document_id: int,
    window_index: int,
    window: dict,
    analysis: dict,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO document_analysis_windows(
                project_id, document_id, window_index, start_node_index,
                end_node_index, source_chars, source_fingerprint,
                locator_start, locator_end, summary, analysis_json,
                model_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id, window_index) DO UPDATE SET
                start_node_index = excluded.start_node_index,
                end_node_index = excluded.end_node_index,
                source_chars = excluded.source_chars,
                source_fingerprint = excluded.source_fingerprint,
                locator_start = excluded.locator_start,
                locator_end = excluded.locator_end,
                summary = excluded.summary,
                analysis_json = excluded.analysis_json,
                model_id = excluded.model_id,
                created_at = excluded.created_at
            """,
            (
                project_id,
                document_id,
                window_index,
                int(window["start_node_index"]),
                int(window["end_node_index"]),
                int(window["source_chars"]),
                window.get("source_fingerprint") or document_window_fingerprint(window),
                window.get("locator_start"),
                window.get("locator_end"),
                str(analysis.get("summary") or "")[:6000],
                json.dumps(analysis, ensure_ascii=False),
                settings.cloudru_model_id,
                utc_now(),
            ),
        )


async def _recursive_synthesis(title: str, analyses: list[dict]) -> dict:
    if not analyses:
        return {}

    current = analyses
    level = 0
    while len(current) > 1:
        level += 1
        groups: list[list[dict]] = []
        group: list[dict] = []
        size = 0
        for item in current:
            rendered = json.dumps(item, ensure_ascii=False)
            if (
                group
                and size + len(rendered) > SYNTHESIS_INPUT_CHARS
                and len(group) >= 2
            ):
                groups.append(group)
                group = []
                size = 0
            group.append(item)
            size += len(rendered)
        if group:
            groups.append(group)

        if len(groups) == 1:
            return await synthesize_document_analysis(title, groups[0], level=level)

        next_level: list[dict] = []
        for group_index, items in enumerate(groups, start=1):
            result = await synthesize_document_analysis(
                f"{title} · synthesis group {group_index}/{len(groups)}",
                items,
                level=level,
            )
            next_level.append(result)
        current = next_level

    if len(current) == 1 and level == 0:
        return await synthesize_document_analysis(title, current, level=1)
    return current[0]


async def deep_analyze_document(
    project_id: int,
    document_id: int,
    *,
    task_id: int | None = None,
    force: bool = False,
) -> dict:
    init_document_intelligence_db()
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        profile = rebuild_document_intelligence(project_id, document_id)
    if profile.get("status") in {"needs_ocr", "unsupported"}:
        raise ValueError(profile.get("last_error") or "Документ нельзя анализировать без извлечённого текста.")

    profile, windows = build_document_windows(project_id, document_id)

    reusable: dict[int, dict] = {}
    with connect() as conn:
        if force:
            conn.execute(
                "DELETE FROM document_analysis_windows WHERE document_id = ?",
                (document_id,),
            )
        else:
            existing_rows = conn.execute(
                """
                SELECT * FROM document_analysis_windows
                WHERE document_id = ? AND project_id = ?
                ORDER BY window_index ASC
                """,
                (document_id, project_id),
            ).fetchall()
            for row in existing_rows:
                item = dict(row)
                reusable[int(item["window_index"])] = item

        conn.execute(
            """
            UPDATE document_intelligence
            SET status = 'analyzing', analyzed_chars = 0, coverage_ratio = 0.0,
                analysis_model = ?, last_error = NULL, updated_at = ?
            WHERE document_id = ? AND project_id = ?
            """,
            (settings.cloudru_model_id, utc_now(), document_id, project_id),
        )

    analyses: list[dict] = []
    analyzed_chars = 0
    total_chars = max(1, int(profile.get("char_count") or 0))
    try:
        for index, window in enumerate(windows, start=1):
            saved = reusable.get(index)
            if (
                saved
                and str(saved.get("source_fingerprint") or "")
                    == str(window.get("source_fingerprint") or "")
                and int(saved.get("source_chars") or -1)
                    == int(window["source_chars"])
            ):
                analysis = _loads(saved.get("analysis_json"), {})
                if analysis:
                    analyses.append(analysis)
                    analyzed_chars += int(window["source_chars"])
                    coverage = min(1.0, analyzed_chars / total_chars)
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE document_intelligence
                            SET analyzed_chars = ?, coverage_ratio = ?, updated_at = ?
                            WHERE document_id = ? AND project_id = ?
                            """,
                            (analyzed_chars, coverage, utc_now(), document_id, project_id),
                        )
                    continue
            if task_id is not None and is_task_cancel_requested(task_id):
                coverage = min(1.0, analyzed_chars / total_chars)
                with connect() as conn:
                    conn.execute(
                        """
                        UPDATE document_intelligence
                        SET status = 'partial', analyzed_chars = ?, coverage_ratio = ?,
                            updated_at = ?, last_error = ?
                        WHERE document_id = ? AND project_id = ?
                        """,
                        (
                            analyzed_chars,
                            coverage,
                            utc_now(),
                            "Глубокий анализ остановлен пользователем.",
                            document_id,
                            project_id,
                        ),
                    )
                return {
                    "document_id": document_id,
                    "status": "partial",
                    "cancelled": True,
                    "coverage_ratio": coverage,
                    "windows_completed": len(analyses),
                    "windows_total": len(windows),
                }

            analysis = await analyze_document_window(
                profile.get("title") or f"Документ #{document_id}",
                index,
                len(windows),
                window["content"],
            )
            analysis["window_index"] = index
            analysis["locator_start"] = window.get("locator_start")
            analysis["locator_end"] = window.get("locator_end")
            analyses.append(analysis)
            _save_window(project_id, document_id, index, window, analysis)
            analyzed_chars += int(window["source_chars"])
            coverage = min(1.0, analyzed_chars / total_chars)
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE document_intelligence
                    SET analyzed_chars = ?, coverage_ratio = ?, updated_at = ?
                    WHERE document_id = ? AND project_id = ?
                    """,
                    (analyzed_chars, coverage, utc_now(), document_id, project_id),
                )
            if task_id is not None:
                record_task_event(
                    task_id,
                    "progress",
                    json.dumps(
                        {
                            "document_id": document_id,
                            "window": index,
                            "windows_total": len(windows),
                            "coverage_ratio": round(coverage, 6),
                        },
                        ensure_ascii=False,
                    ),
                )

        synthesis = await _recursive_synthesis(
            profile.get("title") or f"Документ #{document_id}",
            analyses,
        )
        coverage = min(1.0, analyzed_chars / total_chars)
        status = "complete" if coverage >= 0.995 else "partial"
        summary_long = str(
            synthesis.get("summary_long")
            or synthesis.get("summary")
            or ""
        ).strip()
        summary_short = str(
            synthesis.get("summary_short")
            or _extractive_summary(summary_long, 1000)
            or profile.get("summary_short")
            or ""
        ).strip()

        with connect() as conn:
            conn.execute(
                """
                UPDATE document_intelligence
                SET status = ?, analyzed_chars = ?, coverage_ratio = ?,
                    summary_short = ?, summary_long = ?, analysis_json = ?,
                    analysis_model = ?, last_error = NULL, updated_at = ?
                WHERE document_id = ? AND project_id = ?
                """,
                (
                    status,
                    analyzed_chars,
                    coverage,
                    summary_short[:4000],
                    summary_long[:30000],
                    json.dumps(synthesis, ensure_ascii=False),
                    settings.cloudru_model_id,
                    utc_now(),
                    document_id,
                    project_id,
                ),
            )
        result = get_document_intelligence(project_id, document_id) or {}
        result["windows_completed"] = len(analyses)
        result["windows_total"] = len(windows)
        return result
    except Exception as exc:
        coverage = min(1.0, analyzed_chars / total_chars)
        with connect() as conn:
            conn.execute(
                """
                UPDATE document_intelligence
                SET status = ?, analyzed_chars = ?, coverage_ratio = ?,
                    last_error = ?, updated_at = ?
                WHERE document_id = ? AND project_id = ?
                """,
                (
                    "partial" if analyzed_chars else "failed",
                    analyzed_chars,
                    coverage,
                    str(exc)[:2000],
                    utc_now(),
                    document_id,
                    project_id,
                ),
            )
        raise



def enqueue_deep_document_analysis(
    project_id: int,
    document_id: int,
    *,
    force: bool = False,
) -> dict:
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        profile = rebuild_document_intelligence(project_id, document_id)
    if profile.get("status") in {"needs_ocr", "unsupported"}:
        raise ValueError(profile.get("last_error") or "Документ не готов к глубокому анализу.")

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, task_type, payload_json, status,
                   cancel_requested, created_at, started_at, finished_at
            FROM tasks
            WHERE project_id = ?
              AND task_type = 'document_intelligence'
              AND status IN ('queued','running')
            ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()
    for row in rows:
        payload = _loads(row["payload_json"], {})
        if int(payload.get("document_id") or 0) == int(document_id):
            item = dict(row)
            item["payload"] = payload
            item.pop("payload_json", None)
            item["existing"] = True
            return item

    task = create_task(
        project_id,
        "document_intelligence",
        {"document_id": int(document_id), "force": bool(force)},
    )
    with connect() as conn:
        conn.execute(
            """
            UPDATE document_intelligence
            SET status = 'queued', last_error = NULL, updated_at = ?
            WHERE document_id = ? AND project_id = ?
            """,
            (utc_now(), document_id, project_id),
        )
    task["existing"] = False
    return task


def document_intelligence_status(project_id: int) -> dict:
    init_document_intelligence_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT di.status, COUNT(*) AS n
            FROM document_intelligence di
            JOIN documents d ON d.id = di.document_id
            WHERE di.project_id = ? AND d.deleted_at IS NULL
            GROUP BY di.status
            """,
            (project_id,),
        ).fetchall()
        coverage = conn.execute(
            """
            SELECT COALESCE(AVG(di.coverage_ratio), 0.0) AS avg_coverage
            FROM document_intelligence di
            JOIN documents d ON d.id = di.document_id
            WHERE di.project_id = ? AND d.deleted_at IS NULL
            """,
            (project_id,),
        ).fetchone()["avg_coverage"]
    counts = {row["status"]: int(row["n"]) for row in rows}
    return {
        "counts": counts,
        "average_coverage": float(coverage or 0.0),
        "parser_version": PARSER_VERSION,
    }
