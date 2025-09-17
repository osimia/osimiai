import os
from pathlib import Path
from django.conf import settings

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .models import KnowledgeDocument

# Путь к файлу векторной базы
VECTOR_STORE_PATH = os.path.join(settings.BASE_DIR, "vector_store", "faiss_index")

class RAGService:
    def __init__(self):
        # Проверка наличия API ключа
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY не найден в переменных окружения.")
        
        # Инициализация модели для создания эмбеддингов
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        self.vector_store = None
        self._load_vector_store()

    def _load_vector_store(self):
        """Загружает существующую векторную базу или создает новую, если она не найдена."""
        if os.path.exists(VECTOR_STORE_PATH):
            try:
                self.vector_store = FAISS.load_local(VECTOR_STORE_PATH, self.embeddings, allow_dangerous_deserialization=True)
                print("Векторная база успешно загружена.")
            except Exception as e:
                print(f"Ошибка при загрузке векторной базы: {e}")
        else:
            print("Векторная база не найдена. Будет создана новая при обработке первого документа.")
            # Создаем пустую базу, чтобы избежать ошибок при первом поиске
            # Создадим пустую базу с одним фиктивным текстом, чтобы инициализировать ее
            self.vector_store = FAISS.from_texts(["initial"], self.embeddings)

    def _save_vector_store(self):
        """Сохраняет векторную базу в файл."""
        if self.vector_store:
            os.makedirs(os.path.dirname(VECTOR_STORE_PATH), exist_ok=True)
            self.vector_store.save_local(VECTOR_STORE_PATH)
            print(f"Векторная база сохранена в {VECTOR_STORE_PATH}")

    def process_document(self, document_id: int):
        """Обрабатывает один документ: читает, разбивает на части и добавляет в базу."""
        try:
            doc = KnowledgeDocument.objects.get(pk=document_id)
            doc.status = 'processing'
            doc.save()

            # Загрузка и разбивка PDF
            loader = PyPDFLoader(doc.file.path)
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.split_documents(documents)

            # Добавление метаданных к каждому чанку
            for chunk in chunks:
                chunk.metadata['source'] = doc.title
                chunk.metadata['doc_id'] = doc.id

            # Добавление чанков в векторную базу
            if chunks:
                if self.vector_store and self.vector_store.index.ntotal > 0:
                    self.vector_store.add_documents(chunks)
                else:
                    self.vector_store = FAISS.from_documents(chunks, self.embeddings)
                
                self._save_vector_store()
                doc.status = 'ready'
                doc.error_message = ''
            else:
                doc.status = 'error'
                doc.error_message = 'Не удалось извлечь текст из документа.'
            
            doc.save()
            print(f"Документ '{doc.title}' успешно обработан.")

        except Exception as e:
            if 'doc' in locals():
                doc.status = 'error'
                doc.error_message = str(e)
                doc.save()
            print(f"Ошибка при обработке документа {document_id}: {e}")

    def search(self, query: str, k: int = 4) -> list:
        """Выполняет поиск по векторной базе и возвращает k наиболее релевантных чанков."""
        if self.vector_store is None:
            return []
        
        try:
            results = self.vector_store.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
            return []
