import logging
from docx import Document
import zipfile
from bs4 import BeautifulSoup
from pathlib import Path

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache

from .models import MLRequest, MLResult
from .serializers import MLRequestSerializer
from core.models import StoredFile
from .services import run_tesseract, run_spacy
from .tasks import process_file_task, send_telegram_notification
from filemanager.celery import AsyncResult

logger = logging.getLogger(__name__)

# Конфигурация обработки файлов
SUPPORTED_IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp'}
SUPPORTED_TEXT_TYPES = {'.txt', '.docx', '.odt', '.rtf', '.csv'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
PROCESSING_TIMEOUT = 300  # 5 минут


def read_docx(file_path):
    """Улучшенное чтение DOCX с обработкой ошибок"""
    try:
        with zipfile.ZipFile(file_path) as z:
            with z.open('word/document.xml') as f:
                soup = BeautifulSoup(f.read(), 'xml')
                text = ' '.join(p.text for p in soup.find_all('w:p'))
                return text if text.strip() else None
    except Exception as e:
        logger.error(f"DOCX read failed: {str(e)}", exc_info=True)
        return None


def extract_text_from_docx(file_path):
    """Извлечение текста из DOCX с fallback"""
    try:
        # Пробуем стандартный метод
        doc = Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if text.strip():
            return text

        # Fallback метод
        return read_docx(file_path)
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        return None


def extract_text_from_pdf(file_path):
    """Извлечение текста из PDF с помощью pdf2image и Tesseract"""
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(file_path)
        text = ""
        for i, image in enumerate(images):
            text += f"\n\nPage {i + 1}:\n"
            text += pytesseract.image_to_string(image, lang='rus+eng')

        return text if text.strip() else None
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return None


class PredictView(APIView):
    """API для ML-предсказаний с кешированием"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MLRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cache_key = f"ml_request_{request.user.id}_{str(serializer.validated_data)}"
        cached_result = cache.get(cache_key)

        if cached_result:
            return Response(cached_result, status=status.HTTP_200_OK)

        try:
            ml_request = MLRequest.objects.create(
                user=request.user,
                request_type=request.data.get('type', 'unknown'),
                input_data=serializer.validated_data,
                status='pending'
            )

            # В реальном проекте здесь будет вызов ML сервиса
            result = {
                "status": "success",
                "prediction": {"example": "Mock result"},
                "request_id": ml_request.id
            }

            ml_request.status = 'success'
            ml_request.result = result
            ml_request.save()

            cache.set(cache_key, result, timeout=3600)  # Кешируем на 1 час

            return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}", exc_info=True)
            if 'ml_request' in locals():
                ml_request.status = 'failed'
                ml_request.error_message = str(e)
                ml_request.save()
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def _validate_file(file):
    """Расширенная валидация файла"""
    if not file or not hasattr(file, 'file'):
        raise ValueError("Invalid file object")

    if file.file.size > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit")

    file_ext = Path(file.file.name).suffix.lower()
    if file_ext not in SUPPORTED_IMAGE_TYPES | SUPPORTED_TEXT_TYPES:
        raise ValueError(f"Unsupported file type: {file_ext}")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_stored_file(request, file_id=None):
    """Асинхронная обработка файла через Celery"""
    try:
        file = get_object_or_404(StoredFile, id=file_id, user=request.user)
        _validate_file(file)

        # Определяем очередь по размеру файла
        queue = 'high_priority' if file.file.size < (2 * 1024 * 1024) else 'low_priority'

        # Запуск фоновой задачи
        task = process_file_task.apply_async(
            args=[file.id, request.user.id],
            queue=queue
        )

        # Сохраняем task_id в сессии для отслеживания
        if not request.session.get('task_ids'):
            request.session['task_ids'] = []
        request.session['task_ids'].append(task.id)
        request.session.save()

        return JsonResponse({
            "status": "processing",
            "message": "Файл принят в обработку",
            "task_id": task.id,
            "queue": queue,
            "monitor_url": f"/tasks/{task.id}/status/"
        })

    except Exception as e:
        logger.error(f"File processing error: {str(e)}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_task_status(request, task_id):
    """Проверка статуса задачи с подробной информацией"""
    try:
        task = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": task.status,
            "ready": task.ready(),
            "successful": task.successful() if task.ready() else None,
            "result": task.result if task.ready() and task.successful() else None,
            "error": str(task.result) if task.ready() and task.failed() else None
        }

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


def task_status_page(request, task_id):
    """HTML страница для отслеживания статуса задачи"""
    task = AsyncResult(task_id)

    context = {
        'task_id': task_id,
        'status': task.status,
        'result': task.result if task.ready() else None,
        'ready': task.ready(),
        'successful': task.successful() if task.ready() else None
    }

    return render(request, 'ml_api/task_status.html', context)


class MLRequestListView(APIView):
    """Список запросов с расширенной фильтрацией"""
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get(self, request):
        queryset = MLRequest.objects.filter(user=request.user)

        # Фильтрация по типу
        if request_type := request.GET.get('type'):
            queryset = queryset.filter(request_type=request_type)

        # Фильтрация по статусу
        if status := request.GET.get('status'):
            queryset = queryset.filter(status=status)

        queryset = queryset.select_related('result').order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = MLRequestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """Тестовая отправка уведомлений"""
    try:
        message = request.data.get('message', 'Тестовое уведомление')

        # Отправка email
        from django.core.mail import send_mail
        send_mail(
            subject="Тестовое уведомление",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False
        )

        # Отправка Telegram если есть chat_id
        if hasattr(request.user, 'telegram_chat_id') and request.user.telegram_chat_id:
            send_telegram_notification.delay(
                chat_id=request.user.telegram_chat_id,
                text=message
            )

        return JsonResponse({"status": "success", "message": "Уведомления отправлены"})

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


def _process_file_content(file):
    """Улучшенная обработка файлов с поддержкой PDF"""
    file_ext = Path(file.file.name).suffix.lower()
    file_path = str(Path(file.file.path).resolve())

    try:
        if file_ext == '.pdf':
            logger.info(f"Processing PDF file: {file_path}")
            text = extract_text_from_pdf(file_path)

            if not text:
                return {
                    "service": "ocr",
                    "result": {
                        "status": "error",
                        "message": "Не удалось извлечь текст из PDF"
                    }
                }

            return {
                "service": "ner",
                "result": run_spacy(text)
            }

        elif file_ext in SUPPORTED_IMAGE_TYPES:
            logger.info(f"Processing image file: {file_path}")
            with open(file_path, 'rb') as f:
                content = f.read()

            result = run_tesseract(content)
            return {
                "service": "ocr",
                "result": result
            }

        elif file_ext == '.docx':
            logger.info(f"Processing DOCX file: {file_path}")
            text = extract_text_from_docx(file_path)

            if not text:
                return {
                    "service": "ner",
                    "result": {
                        "status": "error",
                        "message": "Не удалось извлечь текст из DOCX"
                    }
                }

            return {
                "service": "ner",
                "result": run_spacy(text)
            }

        else:  # Текстовые файлы
            logger.info(f"Processing text file: {file_path}")
            encodings = ['utf-8', 'cp1251', 'iso-8859-5', 'utf-16']
            text = None

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                        if text.strip():
                            break
                except UnicodeDecodeError:
                    continue

            if not text:
                return {
                    "service": "ner",
                    "result": {
                        "status": "error",
                        "message": "Не удалось определить кодировку файла"
                    }
                }

            return {
                "service": "ner",
                "result": run_spacy(text)
            }

    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
        return {
            "service": "ocr" if file_ext in SUPPORTED_IMAGE_TYPES else "ner",
            "result": {
                "status": "error",
                "message": f"Ошибка обработки файла: {str(e)}"
            }
        }