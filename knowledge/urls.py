from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    # Список документов
    path('', views.document_list, name='document_list'),
    
    # Загрузка документа
    path('upload/', views.upload_document, name='upload_document'),
    
    # Детали документа
    path('document/<int:pk>/', views.document_detail, name='document_detail'),
    
    # Удаление документа
    path('delete/<int:pk>/', views.delete_document, name='delete_document'),
    
    # Переобработка документа
    path('reprocess/<int:pk>/', views.reprocess_document, name='reprocess_document'),
    path('process-all/', views.process_all_documents, name='process_all_documents'),
    
    # Поиск документов
    path('search/', views.search_documents, name='search_documents'),
    
    # API для поиска (для использования в чате)
    path('api/search/', views.api_search, name='api_search'),
]
