from django.urls import path

from . import views
from .views import PredictView, process_stored_file

urlpatterns = [
    path('api/ml/predict/', PredictView.as_view(), name='ml_predict'),
    path('files/<int:file_id>/process/', process_stored_file, name='process_file'),
]