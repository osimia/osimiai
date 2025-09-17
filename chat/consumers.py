import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatSession, Message
from .utils import generate_chat_title
from services.gemini_client import GeminiClient, get_system_instruction
from knowledge.rag_service import RAGService
import os

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"chat_{self.session_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Проверка, что сессия принадлежит пользователю
        if not await self.user_can_access_session():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.session_group_name, self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.session_group_name, self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get("message", "").strip()

        if not message_text:
            return

        # Сохраняем сообщение пользователя
        await self.save_message(message_text, "user")

        # Обновляем название чата, если это первое сообщение пользователя
        await self.update_chat_title_if_needed(message_text)

        # Запускаем генерацию ответа в фоне
        history = await self.get_history()
        system_instruction = await self.get_system_instruction_from_db()

        # RAG: Ищем релевантный контекст в базе знаний
        rag_service = RAGService()
        search_results = await database_sync_to_async(rag_service.search)(message_text)
        rag_context = ""
        sources = []
        if search_results:
            rag_context = "\n\n".join([doc.page_content for doc in search_results])
            # Собираем уникальные источники
            seen_sources = set()
            for doc in search_results:
                source_title = doc.metadata.get('source', 'Неизвестный источник')
                if source_title not in seen_sources:
                    sources.append({'title': source_title})
                    seen_sources.add(source_title)

        client = GeminiClient()
        try:
            # Адаптируем вызов для стриминга
            response_stream = await database_sync_to_async(client.generate_stream)(
                history=history,
                user_text=message_text,
                system_instruction=system_instruction,
                rag_context=rag_context
            )
            
            assistant_message = ""
            for chunk in response_stream:
                assistant_message += chunk.text
                await self.send(text_data=json.dumps({"message": chunk.text, "type": "chunk"}))
            
            # Сохраняем полный ответ ассистента
            await self.save_message(assistant_message, "assistant", model=client.default_model)

            # Отправляем источники после полного ответа
            if sources:
                await self.send(text_data=json.dumps({"sources": sources, "type": "sources"}))

        except Exception as e:
            error_message = f"Ошибка: {e}"
            await self.send(text_data=json.dumps({"message": error_message, "type": "error"}))
            await self.save_message(error_message, "assistant")

    @database_sync_to_async
    def user_can_access_session(self):
        return ChatSession.objects.filter(pk=self.session_id, user=self.user).exists()

    @database_sync_to_async
    def save_message(self, content, role, model=""):
        session = ChatSession.objects.get(pk=self.session_id)
        Message.objects.create(session=session, role=role, content=content, model=model)
        # Обновляем сессию, чтобы она была вверху списка
        session.save()

    @database_sync_to_async
    def get_history(self):
        return list(ChatSession.objects.get(pk=self.session_id).messages.all().order_by('created_at'))

    @database_sync_to_async
    def get_system_instruction_from_db(self):
        # В будущем можно будет брать из модели SystemPolicy
        return get_system_instruction()

    @database_sync_to_async
    def update_chat_title_if_needed(self, message_text):
        """
        Обновляет название чата, если это первое пользовательское сообщение
        и название еще не было изменено пользователем.
        """
        session = ChatSession.objects.get(pk=self.session_id)
        
        # Проверяем, сколько пользовательских сообщений уже есть
        user_messages_count = session.messages.filter(role='user').count()
        
        # Если это первое пользовательское сообщение и название стандартное
        if user_messages_count == 1 and (not session.title or session.title == "Новый диалог"):
            new_title = generate_chat_title(message_text)
            session.title = new_title
            session.save(update_fields=['title'])
