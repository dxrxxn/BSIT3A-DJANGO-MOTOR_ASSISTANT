from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='dashboard'),
    path('home/', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('jarvis/chat/', views.jarvis_chat, name='jarvis_chat'),
    path('jarvis/status/', views.jarvis_status, name='jarvis_status'),
]