import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from .models import KnowledgeDocument
from .document_processor import DocumentProcessor
from .chroma_service import ChromaService


@login_required
def document_list(request):
    """Список загруженных документов"""
    documents = KnowledgeDocument.objects.filter(
        uploaded_by=request.user
    ).order_by('-created_at') if request.user.is_authenticated else KnowledgeDocument.objects.none()
    
    # Пагинация
    paginator = Paginator(documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Статистика ChromaDB
    try:
        chroma_service = ChromaService()
        stats = chroma_service.get_collection_stats()
    except Exception:
        stats = {'total_documents': 0, 'total_chunks': 0}
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'document_types': KnowledgeDocument.DOCUMENT_TYPES,
    }
    
    return render(request, 'knowledge/document_list.html', context)


@login_required
@require_http_methods(["POST"])
def upload_document(request):
    """Загрузка нового документа"""
    try:
        # Проверяем файл
        if 'file' not in request.FILES:
            messages.error(request, 'Файл не выбран')
            return redirect('knowledge:document_list')
        
        file = request.FILES['file']
        title = request.POST.get('title', '').strip()
        document_type = request.POST.get('document_type', 'law')
        description = request.POST.get('description', '').strip()
        
        # Валидация
        if not file.name.lower().endswith('.pdf'):
            messages.error(request, 'Поддерживаются только PDF файлы')
            return redirect('knowledge:document_list')
        
        if file.size > 50 * 1024 * 1024:  # 50MB
            messages.error(request, 'Размер файла не должен превышать 50MB')
            return redirect('knowledge:document_list')
        
        if not title:
            title = file.name.rsplit('.', 1)[0]
        
        # Проверяем дубликаты
        existing = KnowledgeDocument.objects.filter(
            uploaded_by=request.user,
            title=title
        ).exists()
        
        if existing:
            messages.error(request, f'Документ с названием "{title}" уже существует')
            return redirect('knowledge:document_list')
        
        # Создаем документ
        with transaction.atomic():
            document = KnowledgeDocument.objects.create(
                title=title,
                document_type=document_type,
                file=file,
                uploaded_by=request.user,
                status='pending'
            )
            
            # Добавляем описание если есть
            if description:
                document.description = description
                document.save()
            
            # Запускаем обработку в фоне
            processor = DocumentProcessor()
            success = processor.process_document(document)
            
            if success:
                messages.success(request, f'Документ "{title}" успешно загружен и обработан')
            else:
                messages.warning(request, f'Документ "{title}" загружен, но произошла ошибка при обработке')
    
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке документа: {str(e)}')
    
    return redirect('knowledge:document_list')


@login_required
def process_all_documents(request):
    """Обработка всех необработанных документов"""
    if request.method == 'POST':
        try:
            processor = DocumentProcessor()
            documents = KnowledgeDocument.objects.filter(
                uploaded_by=request.user,
                status__in=['uploaded', 'error']
            )
            
            success_count = 0
            error_count = 0
            
            for document in documents:
                success = processor.process_document(document)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            
            if success_count > 0:
                messages.success(request, f'Успешно обработано {success_count} документов')
            if error_count > 0:
                messages.warning(request, f'Ошибка при обработке {error_count} документов')
                
        except Exception as e:
            messages.error(request, f'Ошибка при обработке документов: {str(e)}')
    
    return redirect('knowledge:document_list')


@login_required
def document_detail(request, pk):
    """Детальная информация о документе"""
    document = get_object_or_404(
        KnowledgeDocument,
        pk=pk,
        uploaded_by=request.user
    )
    
    # Получаем превью
    processor = DocumentProcessor()
    preview = processor.get_document_preview(document)
    
    # Получаем фрагменты документа
    chunks = document.chunks.all()[:10]  # Первые 10 фрагментов
    
    context = {
        'document': document,
        'preview': preview,
        'chunks': chunks,
        'total_chunks': document.chunks.count(),
    }
    
    return render(request, 'knowledge/document_detail.html', context)


@login_required
@require_http_methods(["POST"])
def delete_document(request, pk):
    """Удаление документа"""
    document = get_object_or_404(
        KnowledgeDocument,
        pk=pk,
        uploaded_by=request.user
    )
    
    try:
        with transaction.atomic():
            # Удаляем из ChromaDB
            chroma_service = ChromaService()
            chroma_service.delete_document(document)
            
            # Удаляем файл
            if document.file and os.path.exists(document.file.path):
                os.remove(document.file.path)
            
            title = document.title
            document.delete()
            
            messages.success(request, f'Документ "{title}" успешно удален')
    
    except Exception as e:
        messages.error(request, f'Ошибка при удалении документа: {str(e)}')
    
    return redirect('knowledge:document_list')


@login_required
@require_http_methods(["POST"])
def reprocess_document(request, pk):
    """Переобработка документа"""
    document = get_object_or_404(
        KnowledgeDocument,
        pk=pk,
        uploaded_by=request.user
    )
    
    try:
        processor = DocumentProcessor()
        success = processor.reprocess_document(document)
        
        if success:
            messages.success(request, f'Документ "{document.title}" успешно переобработан')
        else:
            messages.error(request, f'Ошибка при переобработке документа "{document.title}"')
    
    except Exception as e:
        messages.error(request, f'Ошибка при переобработке: {str(e)}')
    
    return redirect('knowledge:document_detail', pk=pk)


@login_required
def search_documents(request):
    """Поиск по документам"""
    query = request.GET.get('q', '').strip()
    document_types = request.GET.getlist('types')
    
    results = []
    
    if query:
        try:
            chroma_service = ChromaService()
            results = chroma_service.search_documents(
                query=query,
                limit=20,
                document_types=document_types if document_types else None
            )
        except Exception as e:
            messages.error(request, f'Ошибка при поиске: {str(e)}')
    
    context = {
        'query': query,
        'results': results,
        'selected_types': document_types,
        'document_types': KnowledgeDocument.DOCUMENT_TYPES,
    }
    
    return render(request, 'knowledge/search.html', context)


@login_required
def api_search(request):
    """API для поиска документов (для использования в чате)"""
    query = request.GET.get('q', '').strip()
    limit = min(int(request.GET.get('limit', 5)), 20)
    
    if not query:
        return JsonResponse({'results': []})
    
    try:
        chroma_service = ChromaService()
        results = chroma_service.search_documents(
            query=query,
            limit=limit
        )
        
        return JsonResponse({
            'results': results,
            'query': query,
            'total': len(results)
        })
    
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'results': []
        }, status=500)
