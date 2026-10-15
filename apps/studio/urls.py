from django.urls import path
from . import views

app_name = 'studio'

urlpatterns = [
    path('',                           views.studio_index,   name='index'),
    path('upload/',                    views.upload_image,   name='upload'),
    path('jobs/start/',                views.start_job,      name='start_job'),
    path('jobs/<str:job_id>/',         views.poll_job,       name='poll_job'),
    path('jobs/<str:job_id>/stream/',  views.stream_job,     name='stream_job'),
    path('jobs/history/',              views.job_history,    name='job_history'),
    path('jobs/<str:job_id>/download/<str:fmt>/', views.download_export, name='download'),
    path('health/',                    views.health,         name='health'),
]
