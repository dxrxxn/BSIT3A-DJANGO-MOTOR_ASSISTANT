from django.urls import path
from . import views

app_name = 'motor'

urlpatterns = [
    path('viewer/', views.viewer_3d, name='viewer_3d'),
    path('upload/', views.upload_model, name='upload_model'),
    path('delete-image/', views.delete_model_image, name='delete_model_image'),
    path('reconstruct/', views.reconstruct_3d, name='reconstruct_3d'),
]
