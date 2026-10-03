from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

PERSONA_VERSION = "2.0.0"
_DATA_DIR = Path(__file__).resolve().parent / "persona_data"
_PART_PATTERN = "MIYORI_BIOGRAPHY_RU_v2.0.0.part*"

_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "greeting": ("привет", "здравств", "добрый день", "добро пожаловать"),
    "morning": ("утро", "утром", "проснул"),
    "evening": ("вечер", "вечером", "ночь", "спать"),
    "care": ("помоги", "тяжело", "устал", "не могу", "сложно"),
    "tenderness": ("нежн", "ласк", "тепл", "мягче"),
    "love": ("люб", "романтик", "чувств"),
    "devotion": ("служ", "предан", "господин"),
    "trust": ("довер", "честн", "точн", "проверь"),
    "playfulness": ("шут", "игрив", "хитр", "лиса"),
    "fox_self": ("ушк", "хвост", "кицун", "лис"),
    "work_start": ("сделай", "создай", "проверь", "разбери", "проанализ", "исправ", "найди"),
    "work_flow": ("дальше", "продолж", "этап", "процесс"),
    "precision": ("точно", "проверь", "свер", "ошибк", "источник"),
    "uncertainty": ("не уверен", "неизвест", "возможно", "может быть"),
    "disagreement": ("не соглас", "возраз", "мнение"),
    "correction": ("ошиб", "исправ", "неверн", "поправ"),
    "success": ("получилось", "готово", "успех", "сделал"),
    "memory": ("памят", "помни", "вспомни", "сохрани"),
    "initiative": ("предлож", "что дальше", "улучш", "оптимиз"),
    "learning": ("учись", "развив", "обратная связь", "стиль"),
    "comfort": ("плохо", "тяжело", "груст", "устал"),
    "quiet": ("тихо", "короче", "пауза", "не говори"),
    "creativity": ("идея", "красив", "дизайн", "придум", "твор"),
    "gratitude": ("спасибо", "благодар"),
    "preferences": ("говори", "стиль", "тон", "короче", "подробнее"),
    "romantic_scene": ("сцена", "романтич", "представь"),
    "return": ("вернулся", "продолжим", "снова"),
    "farewell": ("пока", "до встречи", "доброй ночи"),
}

_DIALOGUE_HINTS: dict[str, tuple[str, ...]] = {
    "identity": ("кто ты", "тебя зовут", "характер", "сколько лет", "миёри"),
    "morning_dialogue": ("утро", "утром"),
    "returning_dialogue": ("вернулся", "продолжим", "снова"),
    "everyday_care": ("помоги", "сложно", "много дел"),
    "tiredness_dialogue": ("устал", "нет сил"),
}


@lru_cache(maxsize=1)
def load_persona_corpus() -> dict:
    parts = sorted(_DATA_DIR.glob(_PART_PATTERN))
    if not parts:
        raise RuntimeError("Persona corpus v2.0.0 не найден.")
    raw = "\n".join(part.read_text(encoding="utf-8") for part in parts)
    data = json.loads(raw)
    if data.get("document_type") != "character_biography_and_speech_corpus":
        raise RuntimeError("Неожиданный формат Persona corpus.")
    if data.get("content_version") != PERSONA_VERSION:
        raise RuntimeError("Версия Persona corpus не совпадает с runtime.")
    return data


def persona_metadata() -> dict:
    data = load_persona_corpus()
    summary = data.get("content_summary", {})
    return {
        "version": data.get("content_version"),
        "title": data.get("title"),
        "biography_sections": summary.get("biography_sections", 0),
        "phrases": summary.get("phrases", 0),
        "dialogues": summary.get("dialogues", 0),
        "language": data.get("language"),
    }


def _message_text(messages: list[dict[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            return str(item.get("content", "")).strip()
    return ""


def _stable_pick(items: list[dict], seed: str) -> dict | None:
    if not items:
        return None
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return items[int.from_bytes(digest[:4], "big") % len(items)]


def _select_categories(message: str, limit: int = 3) -> list[str]:
    text = message.lower()
    scored: list[tuple[int, str]] = []
    for category, hints in _CATEGORY_HINTS.items():
        score = sum(1 for hint in hints if hint in text)
        if score:
            scored.append((score, category))
    scored.sort(key=lambda item: (-item[0], item[1]))
    categories = [category for _, category in scored[:limit]]
    if not categories:
        categories = ["work_start", "trust"] if len(message) > 20 else ["greeting", "trust"]
    return categories[:limit]


def _select_phrases(data: dict, message: str, limit: int = 4) -> list[str]:
    categories = _select_categories(message)
    entries = data.get("phrase_library", {}).get("entries", [])
    selected: list[str] = []
    for category in categories:
        candidates = [item for item in entries if item.get("category") == category]
        item = _stable_pick(candidates, f"{message}|{category}")
        if item and item.get("text"):
            selected.append(str(item["text"]))
        if len(selected) >= limit:
            break
    return selected


def _select_dialogue(data: dict, message: str) -> dict | None:
    text = message.lower()
    category = None
    for candidate, hints in _DIALOGUE_HINTS.items():
        if any(hint in text for hint in hints):
            category = candidate
            break
    if not category:
        return None
    entries = [
        item for item in data.get("dialogue_library", {}).get("entries", [])
        if item.get("category") == category and item.get("is_user_history") is False
    ]
    return _stable_pick(entries, f"dialogue|{message}|{category}")


def _select_biography_section(data: dict, message: str) -> dict | None:
    text = message.lower()
    persona_query = any(
        token in text
        for token in ("миёри", "миё", "кто ты", "о тебе", "характер", "биограф", "любов", "кицун", "лиса", "господин")
    )
    if not persona_query:
        return None
    words = {w for w in re.findall(r"[а-яёa-z0-9]+", text) if len(w) >= 4}
    best: tuple[int, dict] | None = None
    for section in data.get("biography", {}).get("sections", []):
        haystack = (section.get("title", "") + " " + " ".join(section.get("paragraphs", []))).lower()
        score = sum(1 for word in words if word in haystack)
        if best is None or score > best[0]:
            best = (score, section)
    return best[1] if best and best[0] > 0 else None


def build_persona_context(messages: list[dict[str, str]]) -> str:
    data = load_persona_corpus()
    message = _message_text(messages)
    identity = data["identity"]
    core = data["character_core"]
    policy = data["speech_policy"]

    lines = [
        "КАНОНИЧЕСКАЯ ЛИЧНОСТЬ МИЁРИ (Persona Pack v2.0.0):",
        f"- Имя: {identity['name']}; ласковое имя: {identity['nickname']}; возраст образа: {identity['age_years']}.",
        f"- Образ: {identity['species']}; роль: {identity['role']}.",
        f"- Основные черты: {', '.join(core['traits'])}.",
        f"- Обращение: «{policy['primary_address']}»; {policy['address_rule']}",
        f"- Базовый тон: {', '.join(policy['default_tone'])}.",
        "- Актуальная просьба пользователя важнее стилистических примеров.",
        "- Художественная биография Миёри не является историей пользователя.",
        "- Вымышленные диалоги и сцены — только примеры речи, не реальные прошлые события.",
        "- Не заявляй о памяти, проверке, действии или результате без фактического подтверждения приложения.",
        "- На прямые вопросы о природе AI отвечай честно; художественный образ не отменяет фактических ограничений системы.",
    ]

    section = _select_biography_section(data, message)
    if section:
        excerpt = " ".join(section.get("paragraphs", []))[:1200]
        lines.extend([
            "",
            f"Релевантный раздел биографии: {section.get('title')}",
            excerpt,
        ])

    phrases = _select_phrases(data, message)
    if phrases:
        lines.extend([
            "",
            "Примеры манеры для текущего контекста (не копируй механически):",
            *[f"- {item}" for item in phrases],
        ])

    dialogue = _select_dialogue(data, message)
    if dialogue:
        lines.extend(["", f"Пример диалога: {dialogue.get('title', '')}"])
        for turn in dialogue.get("turns", [])[:4]:
            role = "Господин" if turn.get("role") == "user" else "Миёри"
            lines.append(f"- {role}: {turn.get('content', '')}")

    return "\n".join(lines)
