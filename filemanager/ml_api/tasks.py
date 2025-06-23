# ml_api/tasks.py
import logging
from celery import shared_task
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from core.models import StoredFile
from ml_api.services import (
    process_image_with_ocr,
    process_text_with_ner,
    extract_text_from_pdf,
    extract_text_from_docx
)
import time
from pathlib import Path

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_file_task(self, file_id, user_id):
    try:
        file = StoredFile.objects.get(id=file_id, user_id=user_id)
        file.mark_processing()

        file_path = file.file.path
        file_ext = Path(file_path).suffix.lower()

        result = None

        # Process based on file type
        if file_ext in settings.SUPPORTED_IMAGE_TYPES:
            logger.info(f"Processing image file: {file_path}")
            result = process_image_with_ocr(file_path)

        elif file_ext == '.pdf':
            logger.info(f"Processing PDF file: {file_path}")
            text = extract_text_from_pdf(file_path)
            if text:
                result = process_text_with_ner(text)

        elif file_ext == '.docx':
            logger.info(f"Processing DOCX file: {file_path}")
            text = extract_text_from_docx(file_path)
            if text:
                result = process_text_with_ner(text)

        elif file_ext in settings.SUPPORTED_TEXT_TYPES:
            logger.info(f"Processing text file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            result = process_text_with_ner(text)

        if result and result.get('status') == 'success':
            from ml_api.models import AnalysisResult
            AnalysisResult.objects.create(
                file=file,
                result_type=result['type'],
                data=result['data'],
                metadata=result.get('metadata', {})
            )
            file.mark_completed()
            send_processing_notification.delay(user_id, file_id, True)
            return {'status': 'success', 'file_id': file_id}
        else:
            file.mark_failed()
            send_processing_notification.delay(user_id, file_id, False)
            return {'status': 'failed', 'file_id': file_id}

    except Exception as e:
        logger.error(f"Error processing file {file_id}: {str(e)}")
        file.mark_failed()
        send_processing_notification.delay(user_id, file_id, False)
        raise self.retry(exc=e, countdown=60)


@shared_task
def send_processing_notification(user_id, file_id, success):
    try:
        from django.contrib.auth import get_user_model
        from core.models import StoredFile

        User = get_user_model()
        user = User.objects.get(id=user_id)
        file = StoredFile.objects.get(id=file_id)

        subject = "Обработка файла завершена" if success else "Ошибка обработки файла"
        message = (
            f"Файл {file.filename()} был {'успешно обработан' if success else 'не обработан'}.\n\n"
            f"Вы можете просмотреть результаты на сайте: {settings.SITE_URL}/files/{file_id}/"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        # Send Telegram notification if configured
        if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
            from ml_api.telegram import send_telegram_message
            send_telegram_message.delay(
                chat_id=user.telegram_chat_id,
                text=f"{subject}\n{message}"
            )

    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")


@shared_task
def send_telegram_notification(chat_id: str, message: str):
    """Отправка уведомления в Telegram"""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return

    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {str(e)}")
        return False