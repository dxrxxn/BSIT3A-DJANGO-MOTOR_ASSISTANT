from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='dashboard'),
    path('home/', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Structured assistant
    path('jarvis/chat/', views.jarvis_chat, name='jarvis_chat'),
    path('jarvis/image/upload/', views.jarvis_image_upload, name='jarvis_image_upload'),
    path('jarvis/image/<int:image_id>/', views.jarvis_image, name='jarvis_image'),
    path('jarvis/status/', views.jarvis_status, name='jarvis_status'),
]
