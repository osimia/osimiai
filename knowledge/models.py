from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class KnowledgeDocument(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает обработки'),
        ('processing', 'В обработке'),
        ('ready', 'Готов'),
        ('error', 'Ошибка'),
    )
    
    DOCUMENT_TYPES = (
        ('constitution', 'Конституция'),
        ('civil_code', 'Гражданский кодекс'),
        ('criminal_code', 'Уголовный кодекс'),
        ('labor_code', 'Трудовой кодекс'),
        ('family_code', 'Семейный кодекс'),
        ('administrative_code', 'Административный кодекс'),
        ('tax_code', 'Налоговый кодекс'),
        ('federal_law', 'Федеральный закон'),
        ('regulation', 'Постановление'),
        ('other', 'Другое'),
    )

    title = models.CharField(max_length=255, verbose_name="Название документа")
    description = models.TextField(blank=True, null=True, verbose_name="Описание документа")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other', verbose_name="Тип документа")
    file = models.FileField(upload_to='knowledge_base/', verbose_name="Файл (PDF)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Загружен пользователем")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    error_message = models.TextField(blank=True, null=True, verbose_name="Сообщение об ошибке")
    
    # Метаданные для поиска
    total_chunks = models.IntegerField(default=0, verbose_name="Количество фрагментов")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата обработки")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Документ базы знаний"
        verbose_name_plural = "Документы базы знаний"
        ordering = ['-created_at']


class DocumentChunk(models.Model):
    """Фрагменты документов для векторного поиска"""
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks')
    content = models.TextField(verbose_name="Содержимое фрагмента")
    chunk_index = models.IntegerField(verbose_name="Индекс фрагмента")
    page_number = models.IntegerField(null=True, blank=True, verbose_name="Номер страницы")
    
    # Метаданные для ChromaDB
    chroma_id = models.CharField(max_length=255, unique=True, verbose_name="ID в ChromaDB")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фрагмент документа"
        verbose_name_plural = "Фрагменты документов"
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']

    def __str__(self):
        return f"{self.document.title} - Фрагмент {self.chunk_index}"
