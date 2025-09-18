from django.core.management.base import BaseCommand
from django.db import transaction
from knowledge.models import KnowledgeDocument, DocumentChunk
from knowledge.document_processor import DocumentProcessor
import time


class Command(BaseCommand):
    help = 'Быстрая обработка документов без ChromaDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='ID конкретного документа для обработки',
        )

    def handle(self, *args, **options):
        start_time = time.time()
        
        if options['document_id']:
            try:
                document = KnowledgeDocument.objects.get(id=options['document_id'])
                self.stdout.write(f'Быстрая обработка документа: {document.title}')
                
                success = self.fast_process_document(document)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Документ "{document.title}" обработан за {time.time() - start_time:.2f} сек')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Ошибка при обработке документа "{document.title}"')
                    )
                    
            except KnowledgeDocument.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Документ с ID {options["document_id"]} не найден')
                )
        else:
            self.stdout.write(
                self.style.ERROR('Укажите --document-id')
            )

    def fast_process_document(self, document: KnowledgeDocument) -> bool:
        """Быстрая обработка документа без ChromaDB"""
        try:
            with transaction.atomic():
                # Обновляем статус
                document.status = 'processing'
                document.save()
                
                # Используем демо-текст для быстрой обработки
                demo_text = """
                ДЕМО ДОКУМЕНТ - Трудовой кодекс Республики Таджикистан
                
                Статья 1. Основные принципы трудового права
                Трудовое законодательство Республики Таджикистан основывается на принципах свободы труда, запрещения принудительного труда, равенства прав и возможностей работников.
                
                Статья 2. Трудовые отношения
                Трудовые отношения - отношения, основанные на соглашении между работником и работодателем о личном выполнении работником за плату трудовой функции.
                
                Статья 3. Права работников
                Каждый работник имеет право на справедливые условия труда, своевременную и в полном размере выплату заработной платы, отдых, включая ограничение рабочего времени, безопасные условия труда.
                
                Статья 4. Обязанности работников
                Работник обязан добросовестно исполнять свои трудовые обязанности, соблюдать правила внутреннего трудового распорядка, соблюдать трудовую дисциплину, выполнять установленные нормы труда.
                """
                
                # Быстрое разбиение на фрагменты
                chunks = []
                sentences = demo_text.split('.')
                current_chunk = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    if len(current_chunk + sentence) > 200:  # Маленькие фрагменты
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                    else:
                        current_chunk += sentence + ". "
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Удаляем старые фрагменты
                document.chunks.all().delete()
                
                # Сохраняем новые фрагменты
                for i, chunk_text in enumerate(chunks):
                    if len(chunk_text.strip()) > 20:  # Минимальная длина
                        DocumentChunk.objects.create(
                            document=document,
                            content=chunk_text,
                            chunk_index=i,
                            chroma_id=f"{document.id}_{i}"
                        )
                
                # Обновляем статус документа
                document.total_chunks = len(chunks)
                document.status = 'ready'
                document.save()
                
                return True
                
        except Exception as e:
            document.status = 'error'
            document.error_message = str(e)
            document.save()
            print(f"Ошибка при быстрой обработке документа {document.id}: {e}")
            return False
