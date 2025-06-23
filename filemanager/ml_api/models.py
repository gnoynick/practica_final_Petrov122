from django.db import models
from django.contrib.auth.models import User
from core.models import StoredFile


class MLRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.ForeignKey(StoredFile, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=50)
    status = models.CharField(max_length=10, choices=REQUEST_STATUS_CHOICES, default='pending')
    input_data = models.JSONField()
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'ML запрос'
        verbose_name_plural = 'ML запросы'

    def __str__(self):
        return f"MLRequest #{self.id} ({self.get_status_display()})"


class MLResult(models.Model):
    request = models.OneToOneField(MLRequest, on_delete=models.CASCADE, related_name='ml_result')
    file = models.ForeignKey(StoredFile, on_delete=models.CASCADE)
    result_type = models.CharField(max_length=50)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'ML результат'
        verbose_name_plural = 'ML результаты'

    def __str__(self):
        return f"Result for {self.file.filename()}"