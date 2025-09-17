from django.db.models.signals import post_save
from django.dispatch import receiver
from threading import Thread

from .models import KnowledgeDocument
from .rag_service import RAGService


def process_document_in_background(doc_id):
    """Функция-обертка для запуска обработки в потоке."""
    print(f"Запуск фоновой обработки для документа ID: {doc_id}")
    service = RAGService()
    service.process_document(doc_id)

@receiver(post_save, sender=KnowledgeDocument)
def on_document_save(sender, instance, created, **kwargs):
    """
    Срабатывает после сохранения документа. 
    Если документ новый (created=True), запускает его обработку в фоновом потоке.
    """
    if created:
        print(f"Сигнал: Обнаружен новый документ '{instance.title}' (ID: {instance.id}). Запуск обработки.")
        # Запускаем обработку в отдельном потоке, чтобы не блокировать запрос
        thread = Thread(target=process_document_in_background, args=(instance.id,))
        thread.start()
