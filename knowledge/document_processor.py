import os
import re
from typing import List, Dict, Any
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from .models import KnowledgeDocument

# Try to import PyPDF2, fall back to alternative if not available
try:
    import PyPDF2
    PDF_AVAILABLE = True
    print("PyPDF2 успешно загружен")
except ImportError:
    PDF_AVAILABLE = False
    print("ОШИБКА: PyPDF2 не установлен. Установите: pip install PyPDF2")

# Try to import ChromaService, handle gracefully if dependencies missing
try:
    from .chroma_service import ChromaService
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("Warning: ChromaDB dependencies not available. Vector search will be disabled.")


class DocumentProcessor:
    """Обработчик правовых документов для извлечения текста и создания фрагментов"""
    
    def __init__(self):
        if CHROMA_AVAILABLE:
            self.chroma_service = ChromaService()
        else:
            self.chroma_service = None
        self.chunk_size = 500   # Уменьшенный размер фрагмента для быстрой обработки
        self.chunk_overlap = 50  # Уменьшенное перекрытие

    def extract_text_from_pdf(self, file_path_or_file) -> str:
        """Извлечение текста из PDF файла"""
        if not PDF_AVAILABLE:
            # Возвращаем демо-текст для тестирования
            return """
            ДЕМО ДОКУМЕНТ - Трудовой кодекс Республики Таджикистан
            
            Статья 1. Основные принципы трудового права
            Трудовое законодательство Республики Таджикистан основывается на принципах:
            - свободы труда
            - запрещения принудительного труда
            - равенства прав и возможностей работников
            
            Статья 2. Трудовые отношения
            Трудовые отношения - отношения, основанные на соглашении между работником и работодателем о личном выполнении работником за плату трудовой функции.
            
            Статья 3. Права работников
            Каждый работник имеет право на:
            - справедливые условия труда
            - своевременную и в полном размере выплату заработной платы
            - отдых, включая ограничение рабочего времени
            - безопасные условия труда
            
            Статья 4. Обязанности работников
            Работник обязан:
            - добросовестно исполнять свои трудовые обязанности
            - соблюдать правила внутреннего трудового распорядка
            - соблюдать трудовую дисциплину
            - выполнять установленные нормы труда
            """
        
        try:
            if isinstance(file_path_or_file, (InMemoryUploadedFile, str)):
                if hasattr(file_path_or_file, 'read'):
                    # Это загруженный файл
                    file_content = file_path_or_file.read()
                    pdf_file = BytesIO(file_content)
                else:
                    # Это путь к файлу
                    pdf_file = open(file_path_or_file, 'rb')
            else:
                pdf_file = file_path_or_file
            
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Страница {page_num + 1} ---\n"
                        text += page_text
                except Exception as e:
                    print(f"Ошибка при извлечении текста со страницы {page_num + 1}: {e}")
                    continue
            
            if hasattr(pdf_file, 'close'):
                pdf_file.close()
                
            return text.strip()
            
        except Exception as e:
            print(f"Ошибка при извлечении текста из PDF: {e}")
            return ""

    def clean_text(self, text: str) -> str:
        """Очистка и нормализация текста"""
        # Удаляем лишние пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем специальные символы, но оставляем знаки препинания
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\"\'№]', '', text, flags=re.UNICODE)
        
        # Нормализуем кавычки
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()

    def split_into_chunks(self, text: str) -> List[str]:
        """Разбивка текста на фрагменты с учетом структуры правовых документов"""
        chunks = []
        
        # Сначала пытаемся разбить по статьям
        article_pattern = r'(Статья\s+\d+[^\n]*)'
        articles = re.split(article_pattern, text, flags=re.IGNORECASE)
        
        if len(articles) > 1:
            # Документ содержит статьи
            current_chunk = ""
            
            for i, part in enumerate(articles):
                if not part.strip():
                    continue
                
                # Если это заголовок статьи
                if re.match(article_pattern, part, re.IGNORECASE):
                    if current_chunk and len(current_chunk) > self.chunk_size:
                        chunks.append(self.clean_text(current_chunk))
                        current_chunk = part + " "
                    else:
                        current_chunk += part + " "
                else:
                    # Это содержимое статьи
                    if len(current_chunk + part) > self.chunk_size:
                        if current_chunk:
                            chunks.append(self.clean_text(current_chunk))
                        current_chunk = part
                    else:
                        current_chunk += part
            
            if current_chunk:
                chunks.append(self.clean_text(current_chunk))
        
        else:
            # Обычное разбиение по размеру
            chunks = self._split_by_size(text)
        
        return [chunk for chunk in chunks if len(chunk.strip()) > 50]  # Уменьшенный минимум для быстрой обработки

    def _split_by_size(self, text: str) -> List[str]:
        """Разбивка текста по размеру с учетом предложений"""
        chunks = []
        sentences = re.split(r'[.!?]+', text)
        
        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk + sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(self.clean_text(current_chunk))
                current_chunk = sentence + ". "
            else:
                current_chunk += sentence + ". "
        
        if current_chunk:
            chunks.append(self.clean_text(current_chunk))
            
        return chunks

    def process_document(self, document: KnowledgeDocument) -> bool:
        """Полная обработка документа: извлечение текста, создание фрагментов, добавление в ChromaDB"""
        try:
            # Обновляем статус
            document.status = 'processing'
            document.save()
            
            # Извлекаем текст из PDF
            text = self.extract_text_from_pdf(document.file.path)
            
            if not text:
                raise Exception("Не удалось извлечь текст из документа")
            
            # Разбиваем на фрагменты
            chunks = self.split_into_chunks(text)
            
            if not chunks:
                raise Exception("Не удалось создать фрагменты документа")
            
            # Добавляем в ChromaDB (если доступно)
            if self.chroma_service:
                success = self.chroma_service.add_document_chunks(document, chunks)
                
                if success:
                    document.status = 'ready'
                    document.processed_at = timezone.now()
                    document.save()
                    return True
                else:
                    raise Exception("Ошибка при добавлении в векторную базу данных")
            else:
                # Если ChromaDB недоступно, просто сохраняем фрагменты в базе
                from .models import DocumentChunk
                for i, chunk in enumerate(chunks):
                    DocumentChunk.objects.create(
                        document=document,
                        content=chunk,
                        chunk_index=i,
                        metadata={'source': 'document_processor'}
                    )
                document.status = 'ready'
                document.processed_at = timezone.now()
                document.save()
                return True
                
        except Exception as e:
            document.status = 'error'
            document.error_message = str(e)
            document.save()
            print(f"Ошибка при обработке документа {document.id}: {e}")
            return False

    def reprocess_document(self, document: KnowledgeDocument) -> bool:
        """Переобработка документа (удаление старых данных и создание новых)"""
        try:
            # Удаляем старые данные из ChromaDB
            self.chroma_service.delete_document(document)
            
            # Обрабатываем заново
            return self.process_document(document)
            
        except Exception as e:
            print(f"Ошибка при переобработке документа {document.id}: {e}")
            return False

    def get_document_preview(self, document: KnowledgeDocument, max_length: int = 500) -> str:
        """Получение превью документа"""
        try:
            first_chunk = document.chunks.first()
            if first_chunk:
                content = first_chunk.content
                if len(content) > max_length:
                    content = content[:max_length] + "..."
                return content
            return "Превью недоступно"
        except Exception:
            return "Ошибка при получении превью"
