from .models import ChatSession

def sidebar_sessions(request):
    if request.user.is_authenticated:
        sessions = (
            ChatSession.objects.filter(user=request.user)
            .order_by('-updated_at', '-id')[:30]
        )
    else:
        sessions = []
    return {'sidebar_sessions': sessions}
