from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title or f"Сессия #{self.pk}"


class SystemPolicy(models.Model):
    name = models.CharField(max_length=200, default='default')
    version = models.CharField(max_length=50, default='v1')
    instruction = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'version')

    def __str__(self) -> str:
        return f"{self.name}:{self.version}{' *' if self.is_active else ''}"


class Message(models.Model):
    ROLE_CHOICES = (
        ('system', 'system'),
        ('user', 'user'),
        ('assistant', 'assistant'),
    )
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    model = models.CharField(max_length=100, blank=True)
    tokens_in = models.IntegerField(null=True, blank=True)
    tokens_out = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}"


class DeletionAudit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deletion_audits')
    scope = models.CharField(max_length=50, choices=(('all', 'all'), ('session', 'session')))
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"Удаление {self.scope} пользователем {self.user_id} в {self.deleted_at}"
