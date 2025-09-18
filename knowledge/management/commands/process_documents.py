from django.core.management.base import BaseCommand
from knowledge.models import KnowledgeDocument
from knowledge.document_processor import DocumentProcessor


class Command(BaseCommand):
    help = 'Обработка загруженных документов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='ID конкретного документа для обработки',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Обработать все необработанные документы',
        )

    def handle(self, *args, **options):
        processor = DocumentProcessor()
        
        if options['document_id']:
            # Обработать конкретный документ
            try:
                document = KnowledgeDocument.objects.get(id=options['document_id'])
                self.stdout.write(f'Обработка документа: {document.title}')
                
                success = processor.process_document(document)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'Документ "{document.title}" успешно обработан')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при обработке документа "{document.title}"')
                    )
                    
            except KnowledgeDocument.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Документ с ID {options["document_id"]} не найден')
                )
                
        elif options['all']:
            # Обработать все необработанные документы
            documents = KnowledgeDocument.objects.filter(
                status__in=['uploaded', 'error']
            )
            
            if not documents.exists():
                self.stdout.write('Нет документов для обработки')
                return
                
            self.stdout.write(f'Найдено {documents.count()} документов для обработки')
            
            success_count = 0
            error_count = 0
            
            for document in documents:
                self.stdout.write(f'Обработка: {document.title}')
                
                success = processor.process_document(document)
                
                if success:
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {document.title}')
                    )
                else:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'✗ {document.title}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nОбработка завершена: {success_count} успешно, {error_count} ошибок'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR('Укажите --document-id или --all')
            )
