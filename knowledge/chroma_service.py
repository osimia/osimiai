import os
import json
import uuid
from typing import List, Dict, Any
from django.conf import settings
from .models import KnowledgeDocument, DocumentChunk

# Try to import ChromaDB dependencies
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: ChromaDB not installed. Install with: pip install chromadb")

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("Warning: google-generativeai not installed. Install with: pip install google-generativeai")


class ChromaService:
    """Сервис для работы с ChromaDB и векторным поиском"""
    
    def __init__(self):
        # Настройка ChromaDB
        if not CHROMADB_AVAILABLE:
            self.chroma_client = None
            self.collection = None
            return
            
        self.chroma_client = chromadb.PersistentClient(
            path=os.getenv("CHROMA_DB_PATH", getattr(settings, 'CHROMA_DB_PATH', os.path.join(settings.BASE_DIR, "chroma_db"))),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Создаем коллекцию для правовых документов
        self.collection_name = "legal_documents_tj"
        try:
            self.collection = self.chroma_client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Правовые документы Республики Таджикистан"}
            )
        
        # Настройка Gemini для эмбеддингов
        if GENAI_AVAILABLE:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Генерация эмбеддингов с помощью Gemini (быстрый режим)"""
        if not GENAI_AVAILABLE:
            # Быстрый fallback: простые эмбеддинги
            return [[float(hash(text) % 1000) / 1000] * 384 for text in texts]  # Уменьшенная размерность
        
        try:
            # Пакетная обработка для ускорения
            embeddings = []
            batch_size = 10  # Обрабатываем по 10 текстов за раз
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                for text in batch:
                    # Ограничиваем длину текста для ускорения
                    truncated_text = text[:1000] if len(text) > 1000 else text
                    
                    result = genai.embed_content(
                        model="models/text-embedding-004",
                        content=truncated_text,
                        task_type="retrieval_document"
                    )
                    embeddings.append(result['embedding'])
            return embeddings
        except Exception as e:
            print(f"Ошибка при создании эмбеддингов: {e}")
            # Быстрый fallback
            return [[float(hash(text) % 1000) / 1000] * 384 for text in texts]

    def add_document_chunks(self, document: KnowledgeDocument, chunks: List[str]) -> bool:
        """Добавление фрагментов документа в ChromaDB"""
        if not CHROMADB_AVAILABLE or not self.collection:
            # Если ChromaDB недоступно, сохраняем только в Django
            try:
                for i, chunk_text in enumerate(chunks):
                    DocumentChunk.objects.create(
                        document=document,
                        content=chunk_text,
                        chunk_index=i,
                        chroma_id=f"{document.id}_{i}"
                    )
                document.total_chunks = len(chunks)
                document.status = 'ready'
                document.save()
                return True
            except Exception as e:
                print(f"Ошибка при сохранении фрагментов: {e}")
                return False
        try:
            chunk_ids = []
            chunk_texts = []
            chunk_metadatas = []
            
            for i, chunk_text in enumerate(chunks):
                # Создаем уникальный ID для фрагмента
                chunk_id = f"{document.id}_{i}_{uuid.uuid4().hex[:8]}"
                
                # Сохраняем в Django модель
                chunk_obj = DocumentChunk.objects.create(
                    document=document,
                    content=chunk_text,
                    chunk_index=i,
                    chroma_id=chunk_id
                )
                
                chunk_ids.append(chunk_id)
                chunk_texts.append(chunk_text)
                chunk_metadatas.append({
                    "document_id": str(document.id),
                    "document_title": document.title,
                    "document_type": document.document_type,
                    "chunk_index": i,
                    "django_chunk_id": str(chunk_obj.id)
                })
            
            # Генерируем эмбеддинги
            embeddings = self.generate_embeddings(chunk_texts)
            
            # Добавляем в ChromaDB
            self.collection.add(
                ids=chunk_ids,
                documents=chunk_texts,
                embeddings=embeddings,
                metadatas=chunk_metadatas
            )
            
            # Обновляем статус документа
            document.total_chunks = len(chunks)
            document.status = 'ready'
            document.save()
            
            return True
            
        except Exception as e:
            print(f"Ошибка при добавлении фрагментов: {e}")
            document.status = 'error'
            document.error_message = str(e)
            document.save()
            return False

    def search_documents(self, query: str, limit: int = 5, document_types: List[str] = None) -> List[Dict[str, Any]]:
        """Поиск релевантных документов по запросу"""
        try:
            # Генерируем эмбеддинг для запроса
            query_embedding = self.generate_embeddings([query])[0]
            
            # Формируем фильтры
            where_filter = {}
            if document_types:
                where_filter["document_type"] = {"$in": document_types}
            
            # Поиск в ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter if where_filter else None
            )
            
            # Форматируем результаты
            search_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    search_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if results['distances'] else 0,
                        'document_title': results['metadatas'][0][i].get('document_title', ''),
                        'document_type': results['metadatas'][0][i].get('document_type', ''),
                        'chunk_index': results['metadatas'][0][i].get('chunk_index', 0)
                    })
            
            return search_results
            
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
            return []

    def delete_document(self, document: KnowledgeDocument) -> bool:
        """Удаление документа из ChromaDB"""
        try:
            # Получаем все chunk_id для документа
            chunk_ids = list(document.chunks.values_list('chroma_id', flat=True))
            
            if chunk_ids:
                # Удаляем из ChromaDB
                self.collection.delete(ids=chunk_ids)
            
            # Удаляем из Django
            document.chunks.all().delete()
            
            return True
            
        except Exception as e:
            print(f"Ошибка при удалении документа: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Получение статистики коллекции"""
        try:
            if not CHROMADB_AVAILABLE or not self.collection:
                # Если ChromaDB недоступно, считаем из Django
                total_chunks = DocumentChunk.objects.count()
                total_documents = KnowledgeDocument.objects.filter(status='ready').count()
                return {
                    'total_chunks': total_chunks,
                    'total_documents': total_documents,
                    'collection_name': self.collection_name
                }
            
            count = self.collection.count()
            total_documents = KnowledgeDocument.objects.filter(status='ready').count()
            return {
                'total_chunks': count,
                'total_documents': total_documents,
                'collection_name': self.collection_name
            }
        except Exception as e:
            print(f"Ошибка при получении статистики: {e}")
            total_chunks = DocumentChunk.objects.count()
            total_documents = KnowledgeDocument.objects.filter(status='ready').count()
            return {
                'total_chunks': total_chunks,
                'total_documents': total_documents,
                'collection_name': getattr(self, 'collection_name', 'legal_documents_tj')
            }
