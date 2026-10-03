from __future__ import annotations

from pathlib import Path

import httpx

from .config import settings

_ENV_KEYS = ("CLOUDRU_API_KEY", "CLOUDRU_BASE_URL", "CLOUDRU_MODEL_ID")
_DEFAULT_BASE = "https://foundation-models.api.cloud.ru/v1"


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


async def test_cloudru(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_id: str | None = None,
) -> dict:
    key = (api_key if api_key is not None else settings.cloudru_api_key).strip()
    base = (base_url or settings.cloudru_base_url or _DEFAULT_BASE).strip().rstrip("/")
    model = (model_id if model_id is not None else settings.cloudru_model_id).strip()

    if not key:
        raise ValueError("Введите API-ключ Cloud.ru.")

    headers = {"Authorization": f"Bearer {key}"}
    url = f"{base}/models"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers)

    if response.is_error:
        detail = response.text[:500]
        raise RuntimeError(f"Cloud.ru вернул HTTP {response.status_code}: {detail}")

    data = response.json()
    ids: list[str] = []
    chat_models: list[dict] = []
    if isinstance(data, dict):
        raw = data.get("data")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                model_id = str(item["id"])
                ids.append(model_id)
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                model_type = str(metadata.get("type") or "").lower()
                if not model_type or "llm" in model_type or "chat" in model_type or "text" in model_type:
                    chat_models.append({
                        "id": model_id,
                        "name": metadata.get("name") or model_id,
                        "type": metadata.get("type"),
                    })

    selected_found = bool(model and model in ids) if ids else None
    if model and selected_found is False:
        raise ValueError(
            f"Model ID «{model}» не найден в /models. Выберите точный ID из списка Cloud.ru."
        )

    chat_ok = None
    if model:
        chat_url = f"{base}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Ответь одним словом: OK"}],
            "max_completion_tokens": 8,
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            chat_response = await client.post(
                chat_url,
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
        if chat_response.is_error:
            detail = chat_response.text[:700]
            raise RuntimeError(
                f"Ключ работает, но chat/completions для модели «{model}» вернул "
                f"HTTP {chat_response.status_code}: {detail or 'без текста ошибки'}"
            )
        chat_ok = True

    return {
        "ok": True,
        "models_found": len(ids),
        "selected_model": model or None,
        "selected_model_found": selected_found,
        "chat_ok": chat_ok,
        "chat_models": chat_models[:80],
        "sample_models": ids[:12],
    }
