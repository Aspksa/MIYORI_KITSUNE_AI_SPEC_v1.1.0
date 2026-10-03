from __future__ import annotations

from pathlib import Path

import httpx

from .config import settings

_ENV_KEYS = ("CLOUDRU_API_KEY", "CLOUDRU_BASE_URL", "CLOUDRU_MODEL_ID")
_DEFAULT_BASE = "https://foundation-models.api.cloud.ru/v1"
PREFERRED_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


def _env_path() -> Path:
    return settings.root_dir / ".env"


def _masked_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••••••" + value[-4:]


def cloudru_profile() -> dict:
    return {
        "configured": bool(settings.cloudru_api_key and settings.cloudru_model_id),
        "api_key_set": bool(settings.cloudru_api_key),
        "api_key_masked": _masked_key(settings.cloudru_api_key),
        "base_url": settings.cloudru_base_url,
        "model_id": settings.cloudru_model_id,
        "preferred_model_id": PREFERRED_CHAT_MODEL,
    }


def _env_encode(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _write_env_values(values: dict[str, str]) -> None:
    path = _env_path()
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    replaced: set[str] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        matched = False
        for key in _ENV_KEYS:
            if stripped.startswith(key + "="):
                output.append(f"{key}={_env_encode(values[key])}")
                replaced.add(key)
                matched = True
                break
        if not matched:
            output.append(line)

    if output and output[-1] != "":
        output.append("")

    for key in _ENV_KEYS:
        if key not in replaced:
            output.append(f"{key}={_env_encode(values[key])}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def save_cloudru_profile(
    *,
    api_key: str | None,
    base_url: str | None,
    model_id: str | None,
) -> dict:
    current_key = settings.cloudru_api_key
    new_key = current_key if api_key is None else api_key.strip()
    new_base = (base_url or settings.cloudru_base_url or _DEFAULT_BASE).strip().rstrip("/")
    new_model = (model_id if model_id is not None else settings.cloudru_model_id).strip()

    if not new_base.startswith("https://"):
        raise ValueError("Cloud.ru Base URL должен использовать HTTPS.")

    _write_env_values(
        {
            "CLOUDRU_API_KEY": new_key,
            "CLOUDRU_BASE_URL": new_base,
            "CLOUDRU_MODEL_ID": new_model,
        }
    )

    object.__setattr__(settings, "cloudru_api_key", new_key)
    object.__setattr__(settings, "cloudru_base_url", new_base)
    object.__setattr__(settings, "cloudru_model_id", new_model)

    return cloudru_profile()


async def list_cloudru_models(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict:
    key = (api_key if api_key is not None else settings.cloudru_api_key).strip()
    base = (base_url or settings.cloudru_base_url or _DEFAULT_BASE).strip().rstrip("/")

    if not key:
        raise ValueError("Введите API-ключ Cloud.ru.")

    headers = {"Authorization": f"Bearer {key}"}
    url = f"{base}/models"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers)

    if response.is_error:
        detail = response.text[:700]
        raise RuntimeError(
            f"Cloud.ru /models вернул HTTP {response.status_code}: "
            f"{detail or 'без текста ошибки'}"
        )

    data = response.json()
    models: list[dict] = []
    ids: list[str] = []
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        for item in data["data"]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            model_id = str(item["id"])
            ids.append(model_id)
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            model_type = str(metadata.get("type") or "").strip()
            normalized = model_type.lower()
            is_chat = (
                not normalized
                or "llm" in normalized
                or "chat" in normalized
                or "text" in normalized
            )
            models.append({
                "id": model_id,
                "name": metadata.get("name") or model_id,
                "type": model_type or None,
                "is_chat": is_chat,
                "max_model_len": item.get("max_model_len"),
            })

    chat_models = [item for item in models if item["is_chat"]]
    chat_models.sort(key=lambda item: (item["id"] != PREFERRED_CHAT_MODEL, item["id"].lower()))
    return {
        "ok": True,
        "models_found": len(ids),
        "models": models[:200],
        "chat_models": chat_models[:200],
        "selected_model": settings.cloudru_model_id or None,
        "selected_model_found": bool(settings.cloudru_model_id and settings.cloudru_model_id in ids),
        "preferred_model_id": PREFERRED_CHAT_MODEL,
        "preferred_model_available": PREFERRED_CHAT_MODEL in ids,
    }


async def test_cloudru(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_id: str | None = None,
) -> dict:
    key = (api_key if api_key is not None else settings.cloudru_api_key).strip()
    base = (base_url or settings.cloudru_base_url or _DEFAULT_BASE).strip().rstrip("/")
    model = (model_id if model_id is not None else settings.cloudru_model_id).strip()

    catalog = await list_cloudru_models(api_key=key, base_url=base)
    ids = [item["id"] for item in catalog["models"]]

    if not model:
        return {
            **catalog,
            "ok": False,
            "reason": "model_required",
            "chat_ok": False,
            "selected_model": None,
            "message": "Ключ работает. Выберите Model ID из списка доступных LLM.",
        }

    if model not in ids:
        return {
            **catalog,
            "ok": False,
            "reason": "model_not_found",
            "chat_ok": False,
            "selected_model": model,
            "selected_model_found": False,
            "message": (
                f"«{model}» не является доступным Model ID Foundation Models. "
                "Выберите модель из списка Cloud.ru."
            ),
        }

    chat_url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Ответь одним словом: OK"}],
        "max_completion_tokens": 8,
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        chat_response = await client.post(chat_url, headers=headers, json=payload)

    if chat_response.is_error:
        detail = chat_response.text[:700]
        return {
            **catalog,
            "ok": False,
            "reason": "chat_failed",
            "chat_ok": False,
            "selected_model": model,
            "selected_model_found": True,
            "http_status": chat_response.status_code,
            "message": (
                f"Модель «{model}» найдена, но chat/completions вернул "
                f"HTTP {chat_response.status_code}: {detail or 'без текста ошибки'}"
            ),
        }

    return {
        **catalog,
        "ok": True,
        "reason": None,
        "chat_ok": True,
        "selected_model": model,
        "selected_model_found": True,
        "message": f"Cloud.ru и chat/completions для модели «{model}» работают.",
    }
