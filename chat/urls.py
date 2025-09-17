from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('session/<int:pk>/', views.session_detail, name='session_detail'),
    path('session/<int:pk>/message/', views.post_message, name='post_message'),
    path('session/<int:pk>/delete/', views.delete_session, name='delete_session'),
    path('delete_all/', views.delete_all_data, name='delete_all_data'),
    path('signup/', views.signup, name='signup'),
    path('session/<int:pk>/rename/', views.rename_session, name='rename_session'),
]
