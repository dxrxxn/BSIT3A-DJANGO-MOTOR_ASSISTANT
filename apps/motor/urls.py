from django.urls import path

from . import views

app_name = 'motor'

urlpatterns = [
    path('viewer/', views.viewer, name='viewer'),
]
