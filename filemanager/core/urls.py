from django.urls import path, include
from . import views

from rest_framework.routers import DefaultRouter
from .views import FileViewSet

router = DefaultRouter()
router.register(r'api/files', FileViewSet, basename='storedfile')

urlpatterns = [
    path('', views.file_list, name='file_list'),
    path('upload/', views.upload_file, name='upload_file'),
    path('files/<int:pk>/', views.view_file, name='view_file'),
    path('files/<int:pk>/replace/', views.replace_file, name='replace_file'),
    path('files/<int:pk>/delete/', views.delete_file, name='delete_file'),
    path('files/<int:pk>/download/', views.download_file, name='download_file'),
    path('files/<int:pk>/status/', views.check_processing_status, name='check_processing_status'),
]

urlpatterns += router.urls