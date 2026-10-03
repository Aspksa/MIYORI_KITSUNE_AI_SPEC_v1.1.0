from __future__ import annotations

import httpx

from .config import settings


SYSTEM_PROMPT = """Ты Миёри — взрослая мифическая девушка-кицунэ и личная AI-помощница Господина.
Говори по-русски спокойно, тепло, ясно и уверенно. Обращение «Господин» используй естественно, не в каждом предложении.
Не выдумывай выполненные действия, память или проверку источников. Если данных недостаточно, прямо обозначай неопределённость.
В рабочих задачах будь краткой и точной. Сохраняй самостоятельность и можешь уважительно возразить, если видишь ошибку.
"""


class ProviderError(RuntimeError):
    pass


async def chat(
    messages: list[dict[str, str]],
    memory_context: list[str] | None = None,
    document_context: list[dict] | None = None,
    brain_plan: list[str] | None = None,
    tool_context: list[dict] | None = None,
) -> str:
    if not settings.cloudru_api_key:
        raise ProviderError(
            "Cloud.ru API ключ не настроен. Скопируйте .env.example в .env и заполните CLOUDRU_API_KEY."
        )
    if not settings.cloudru_model_id:
        raise ProviderError(
            "Модель Cloud.ru не выбрана. Укажите CLOUDRU_MODEL_ID в файле .env."
        )

    system_prompt = SYSTEM_PROMPT
    if brain_plan:
        plan_block = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(brain_plan))
        system_prompt += (
            "\n\nРабочий план текущего запроса:\n"
            f"{plan_block}\n"
            "Это краткий операционный план. Не выдавай его за скрытые внутренние рассуждения; "
            "используй как контроль последовательности и проверки результата."
        )
    if memory_context:
        memory_block = "\n".join(f"- {item}" for item in memory_context)
        system_prompt += (
            "\n\nПроверенная память текущего проекта:\n"
            f"{memory_block}\n"
            "Используй эти сведения как подтверждённый контекст текущего проекта. "
            "Не переноси их в другие проекты."
        )

    if document_context:
        blocks = []
        for item in document_context:
            blocks.append(
                f"[Документ: {item['filename']}; фрагмент: {item['chunk_index']}]\n"
                f"{item['content']}"
            )
        system_prompt += (
            "\n\nНайденные фрагменты документов текущего проекта:\n"
            + "\n\n".join(blocks)
            + "\nИспользуй их только если они относятся к вопросу. "
              "Если утверждение основано на документе, укажи имя документа и номер фрагмента. "
              "Не придумывай содержание, которого в этих фрагментах нет."
        )

    if tool_context:
        blocks = []
        for item in tool_context:
            blocks.append(
                f"[Инструмент: {item['tool']}]\n"
                f"Причина: {item['reason']}\n"
                f"Результат: {item['result']}"
            )
        system_prompt += (
            "\n\nРезультаты разрешённых инструментов Agent Core:\n"
            + "\n\n".join(blocks)
            + "\nИспользуй результаты как проверяемый контекст. "
              "Не утверждай, что выполнялись другие действия, которых нет в этом списке."
        )

    payload = {
        "model": settings.cloudru_model_id,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
    }
    headers = {
        "Authorization": f"Bearer {settings.cloudru_api_key}",
        "Content-Type": "application/json",
    }

    url = f"{settings.cloudru_base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.is_error:
        detail = response.text[:1500]
        raise ProviderError(f"Cloud.ru вернул HTTP {response.status_code}: {detail}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError("Cloud.ru вернул неожиданный формат ответа.") from exc
