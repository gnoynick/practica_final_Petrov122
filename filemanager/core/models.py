# core/models.py
import os
import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from pathlib import Path
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

class StoredFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    file = models.FileField(
        upload_to='uploads/%Y/%m/%d/',
        storage=OverwriteStorage(),
        verbose_name='Файл'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')
    description = models.CharField(max_length=100, blank=True, verbose_name='Описание')
    processed = models.BooleanField(default=False, verbose_name='Обработан')
    processing_status = models.CharField(max_length=20, default='pending', verbose_name='Статус обработки')

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename()

    def filename(self):
        return os.path.basename(self.file.name)

    def extension(self):
        return Path(self.file.name).suffix.lower()

    def is_image(self):
        return self.extension() in settings.SUPPORTED_IMAGE_TYPES

    def is_text(self):
        return self.extension() in settings.SUPPORTED_TEXT_TYPES

    def mark_processing(self):
        self.processing_status = 'processing'
        self.save()

    def mark_completed(self):
        self.processed = True
        self.processing_status = 'completed'
        self.save()

    def mark_failed(self):
        self.processing_status = 'failed'
        self.save()

    def delete(self, *args, **kwargs):
        if self.file:
            try:
                os.remove(self.file.path)
            except Exception as e:
                logger.error(f"Error deleting file {self.file.path}: {e}")
        super().delete(*args, **kwargs)