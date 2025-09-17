from django.contrib import admin
from .models import KnowledgeDocument

@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('title',)
    readonly_fields = ('status', 'created_at', 'updated_at', 'error_message')

    fieldsets = (
        (None, {
            'fields': ('title', 'file')
        }),
        ('Статус обработки', {
            'fields': ('status', 'error_message')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )
