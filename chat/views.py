from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.http import JsonResponse, StreamingHttpResponse
import json
import time
from .models import ChatSession, Message, DeletionAudit, SystemPolicy
from .utils import generate_chat_title
from services.gemini_client import GeminiClient, get_system_instruction
from knowledge.rag_service import RAGService
import os


def landing_page(request):
    """Landing page for non-authenticated users"""
    if request.user.is_authenticated:
        return redirect('chat:index')
    return render(request, 'landing.html')


@login_required
@require_http_methods(["GET", "POST"])
def index(request):
    # Создание новой сессии по POST
    if request.method == "POST":
        # Проверяем лимит на создание новых чатов
        if not ChatSession.can_create_new_session(request.user):
            messages.error(request, 'Вы достигли лимита в 5 активных чатов. Удалите или архивируйте старые чаты для создания новых.')
            return redirect('chat:index')
        
        first_prompt = (request.POST.get("first_prompt") or "").strip()
        
        # Автоматически генерируем название на основе первого вопроса
        if first_prompt:
            auto_title = generate_chat_title(first_prompt)
        else:
            auto_title = "Новый диалог"
        
        # Используем переданное название или автоматически сгенерированное
        title = request.POST.get("title") or auto_title
        session = ChatSession.objects.create(user=request.user, title=title)
        # Добавим system сообщение из активной политики (если есть)
        policy = SystemPolicy.objects.filter(is_active=True).order_by('-created_at').first()
        instruction = policy.instruction if policy else get_system_instruction()
        Message.objects.create(session=session, role='system', content=instruction)
        if first_prompt:
            # Сохраняем первое сообщение пользователя и вызываем модель
            Message.objects.create(session=session, role='user', content=first_prompt)
            try:
                if not os.getenv('GEMINI_API_KEY'):
                    raise RuntimeError('GEMINI_API_KEY не задан. Добавьте ключ в .env')
                client = GeminiClient()
                # RAG context - поиск в базе знаний
                rag_context = ""
                try:
                    from knowledge.chroma_service import ChromaService
                    chroma_service = ChromaService()
                    search_results = chroma_service.search_documents(first_prompt, limit=3)
                    if search_results:
                        rag_context = "Контекст из правовых документов Таджикистана:\n\n"
                        for i, result in enumerate(search_results, 1):
                            rag_context += f"{i}. Из документа '{result.get('document_title', 'Неизвестный документ')}':\n"
                            rag_context += f"{result['content'][:400]}...\n\n"
                        rag_context += "Используйте этот контекст для более точного и обоснованного ответа на вопрос пользователя.\n"
                except Exception as e:
                    print(f"Ошибка RAG поиска: {e}")
                    rag_context = ""
                result = client.generate(
                    history=[],
                    user_text=first_prompt,
                    system_instruction=instruction,
                    rag_context=rag_context
                )
                assistant_text = (result.get('text') or '').strip() or 'Не удалось получить ответ от модели.'
                Message.objects.create(session=session, role='assistant', content=assistant_text, model=result.get('model'))
            except Exception as e:
                Message.objects.create(session=session, role='assistant', content=f"Ошибка при обращении к модели: {e}")
        return redirect('chat:session_detail', pk=session.pk)

    return render(request, 'chat/index.html', {})


@login_required
def session_detail(request, pk: int):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    messages_qs = session.messages.all().order_by('created_at', 'pk')
    from django.utils import timezone
    from datetime import timedelta
    twelve_hours_ago = timezone.now() - timedelta(hours=12)
    recent_user_messages_count = session.messages.filter(
        role='user',
        created_at__gte=twelve_hours_ago
    ).count()
    return render(request, 'chat/session_detail.html', {
        'session': session,
        'chat_messages': messages_qs,
        'twelve_hours_ago': twelve_hours_ago,
        'recent_user_messages_count': recent_user_messages_count,
    })


@login_required
@require_http_methods(["POST"])
def post_message(request, pk: int):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    user_text = (request.POST.get('message') or '').strip()
    if not user_text:
        return JsonResponse({'error': 'Введите сообщение'}, status=400)

    # Проверяем лимит сообщений для этого чата
    if not session.can_send_message():
        return JsonResponse({'error': 'Вы достигли лимита в 10 сообщений за 12 часов для этого чата. Попробуйте позже или создайте новый чат.'}, status=429)

    # Сохраняем сообщение пользователя
    Message.objects.create(session=session, role='user', content=user_text)

    # Собираем историю и системную инструкцию
    history = list(session.messages.all().order_by('created_at'))
    system_instruction = get_system_instruction()
    # Ищем системное сообщение в истории, если оно там есть - используем его
    for msg in history:
        if msg.role == 'system':
            system_instruction = msg.content
            break

    def generate_stream():
        try:
            if not os.getenv('GEMINI_API_KEY'):
                yield f"data: {json.dumps({'error': 'GEMINI_API_KEY не задан'})}\n\n"
                return
            
            client = GeminiClient()
            
            # RAG context - поиск в базе знаний
            rag_context = ""
            try:
                from knowledge.chroma_service import ChromaService
                chroma_service = ChromaService()
                search_results = chroma_service.search_documents(user_text, limit=3)
                if search_results:
                    rag_context = "Контекст из правовых документов Таджикистана:\n\n"
                    for i, result in enumerate(search_results, 1):
                        rag_context += f"{i}. Из документа '{result.get('document_title', 'Неизвестный документ')}':\n"
                        rag_context += f"{result['content'][:400]}...\n\n"
                    rag_context += "Используйте этот контекст для более точного и обоснованного ответа на вопрос пользователя.\n"
            except Exception as e:
                print(f"Ошибка RAG поиска: {e}")
                rag_context = ""

            stream = client.generate_stream(
                history=history,
                user_text=user_text,
                system_instruction=system_instruction,
                rag_context=rag_context
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.text:
                    full_response += chunk.text
                    yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"
                    time.sleep(0.01)  # Small delay to simulate typing
            
            # Сохраняем полный ответ в базу данных
            Message.objects.create(
                session=session, 
                role='assistant', 
                content=full_response,
                model=client.default_model
            )
            
            # Обновим updated_at сессии
            ChatSession.objects.filter(pk=session.pk).update()
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            error_msg = f"Ошибка при обращении к модели: {e}"
            Message.objects.create(session=session, role='assistant', content=error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    response = StreamingHttpResponse(generate_stream(), content_type='text/plain')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response


@login_required
@require_http_methods(["POST"])
def delete_session(request, pk: int):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    with transaction.atomic():
        session.delete()
        DeletionAudit.objects.create(user=request.user, scope='session', session=None, note=f'session_id={pk}')
    messages.success(request, 'Сессия удалена')
    return redirect('chat:index')


@login_required
@require_http_methods(["POST"])
def delete_all_data(request):
    with transaction.atomic():
        ChatSession.objects.filter(user=request.user).delete()
        DeletionAudit.objects.create(user=request.user, scope='all', session=None, note='user requested full deletion')
    messages.success(request, 'Вся ваша история удалена')
    return redirect('chat:index')


@require_http_methods(["GET", "POST"])
@login_required
@require_http_methods(["POST"])
def rename_session(request, pk: int):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        if title:
            session.title = title
            session.save(update_fields=['title'])
            return JsonResponse({'status': 'ok', 'title': title})
        return JsonResponse({'status': 'error', 'message': 'Название не может быть пустым'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Неверный формат запроса'}, status=400)

def signup(request):
    if request.user.is_authenticated:
        return redirect('chat:index')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('chat:index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})
