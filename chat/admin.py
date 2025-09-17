from django.contrib import admin
from .models import ChatSession, Message, SystemPolicy, DeletionAudit


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'is_archived', 'created_at', 'updated_at')
    list_filter = ('is_archived', 'created_at')
    search_fields = ('title', 'user__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'model', 'created_at')
    list_filter = ('role', 'model', 'created_at')
    search_fields = ('content',)


@admin.register(SystemPolicy)
class SystemPolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'version', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'version', 'instruction')


@admin.register(DeletionAudit)
class DeletionAuditAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'scope', 'session', 'deleted_at', 'note')
    list_filter = ('scope', 'deleted_at')
    search_fields = ('note', 'user__username')
