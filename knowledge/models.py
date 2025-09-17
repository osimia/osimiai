from django.db import models

class KnowledgeDocument(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает обработки'),
        ('processing', 'В обработке'),
        ('ready', 'Готов'),
        ('error', 'Ошибка'),
    )

    title = models.CharField(max_length=255, verbose_name="Название документа")
    file = models.FileField(upload_to='knowledge_base/', verbose_name="Файл (PDF)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    error_message = models.TextField(blank=True, null=True, verbose_name="Сообщение об ошибке")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Документ базы знаний"
        verbose_name_plural = "Документы базы знаний"
        ordering = ['-created_at']
