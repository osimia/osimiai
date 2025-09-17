import os
from typing import Optional, Dict, Any
from google import genai


class GeminiClient:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY не установлен в окружении")
        self.client = genai.Client(api_key=api_key)
        self.default_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def generate(
        self,
        history: list, # Ожидаем список сообщений
        user_text: str,
        system_instruction: Optional[str] = None,
        rag_context: Optional[str] = None,
        model: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        safety_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        model_name = model or self.default_model
        
        # Формируем историю для API, маппинг ролей
        api_history = []
        for msg in history:
            # Пропускаем системные сообщения, они будут переданы отдельно
            if msg.role == 'system':
                continue
            api_history.append({
                'role': 'model' if msg.role == 'assistant' else msg.role,
                'parts': [{'text': msg.content}]
            })

        # Используем chat session для поддержки контекста
        try:
            model_instance = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            chat = model_instance.start_chat(history=api_history)

            # Формируем финальный промпт с RAG-контекстом
            final_prompt = user_text
            if rag_context:
                final_prompt = f"""Основываясь на следующем контексте, ответь на вопрос.

Контекст:
---
{rag_context}
---

Вопрос: {user_text}
"""

            response = chat.send_message(final_prompt)

        except Exception as e:
            raise RuntimeError(f"Ошибка при вызове модели: {e}") from e

        # Унификация ответа
        text = ""
        try:
            text = response.text
        except Exception:
            # fallback
            if response.candidates:
                text = ''.join(part.text for part in response.candidates[0].content.parts)

        return {
            "text": text or "Не удалось извлечь текст из ответа модели.",
            "raw": response,
            "model": model_name,
        }

    def generate_stream(
        self,
        history: list,
        user_text: str,
        system_instruction: Optional[str] = None,
        rag_context: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        model_name = model or self.default_model
        api_history = []
        for msg in history:
            if msg.role == 'system':
                continue
            api_history.append({
                'role': 'model' if msg.role == 'assistant' else msg.role,
                'parts': [{'text': msg.content}]
            })

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        chat = model_instance.start_chat(history=api_history)

        # Формируем финальный промпт с RAG-контекстом
        final_prompt = user_text
        if rag_context:
            final_prompt = f"""Основываясь на следующем контексте, ответь на вопрос.

Контекст:
---
{rag_context}
---

Вопрос: {user_text}
"""

        return chat.send_message(final_prompt, stream=True)


def get_system_instruction() -> str:
    # Минимальная системная инструкция — далее можно вынести в БД (SystemPolicy)
    return (
        "Ты — AI-ассистент, отвечающий по законодательству Республики Таджикистан. "
        "Твоя задача — отвечать на вопросы пользователя, строго основываясь на предоставленном КОНТЕКСТЕ. "
        "Если в контексте нет ответа, вежливо сообщи об этом и не придумывай информацию. "
        "Отвечай на русском языке. Ответы не являются юридической консультацией."
    )
