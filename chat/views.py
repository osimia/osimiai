from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
import json
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
                # RAG: Ищем релевантный контекст
                rag_service = RAGService()
                search_results = rag_service.search(first_prompt)
                rag_context = ""
                if search_results:
                    rag_context = "\n\n".join([doc.page_content for doc in search_results])

                # При первом сообщении история пуста
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
    return render(request, 'chat/session_detail.html', {
        'session': session,
        'chat_messages': messages_qs,
    })


@login_required
@require_http_methods(["POST"])
def post_message(request, pk: int):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)
    user_text = (request.POST.get('message') or '').strip()
    if not user_text:
        messages.warning(request, 'Введите сообщение')
        return redirect('chat:session_detail', pk=pk)

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

    # Вызов Gemini
    try:
        if not os.getenv('GEMINI_API_KEY'):
            raise RuntimeError('GEMINI_API_KEY не задан. Добавьте ключ в .env')
        client = GeminiClient()
        result = client.generate(
            history=history,
            user_text=user_text,
            system_instruction=system_instruction,
        )
        assistant_text = (result.get('text') or '').strip() or 'Не удалось получить ответ от модели.'
        Message.objects.create(session=session, role='assistant', content=assistant_text, model=result.get('model'))
    except Exception as e:
        Message.objects.create(session=session, role='assistant', content=f"Ошибка при обращении к модели: {e}")

    # Обновим updated_at сессии
    ChatSession.objects.filter(pk=session.pk).update()

    return redirect('chat:session_detail', pk=pk)


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
