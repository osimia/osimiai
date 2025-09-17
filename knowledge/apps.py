from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'

    def ready(self):
        # Импортируем сигналы, чтобы они были зарегистрированы при запуске приложения
        import knowledge.signals
