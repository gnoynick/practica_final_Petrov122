import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import MLRequest
import json

logger = logging.getLogger(__name__)
User = get_user_model()


@csrf_exempt
def telegram_webhook(request):
    """Обработчик входящих сообщений от Telegram"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            text = message.get('text', '').strip().lower()

            logger.info(f"Incoming Telegram message: {text}")

            # Обработка команды /start
            if text.startswith('/start'):
                return handle_start_command(chat_id, text)

            # Обработка команды /help
            elif text == '/help':
                return send_telegram_message(
                    chat_id,
                    "Доступные команды:\n"
                    "/start - Начало работы\n"
                    "/help - Справка\n"
                    "/link <код> - Привязать аккаунт"
                )

            # Обработка команды /link
            elif text.startswith('/link'):
                return handle_link_command(chat_id, text)

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            logger.error(f"Telegram webhook error: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error'}, status=500)

    return JsonResponse({'status': 'method not allowed'}, status=405)


def handle_start_command(chat_id, text):
    """Обработка команды /start"""
    parts = text.split()
    if len(parts) > 1:
        username = parts[1]
        try:
            user = User.objects.get(username=username)
            code = generate_verification_code(user.id)

            message = (
                f"Привет, {user.username}!\n\n"
                f"Ваш код подтверждения: {code}\n\n"
                "Введите его в вашем профиле на сайте или отправьте "
                "команду /link с кодом в этом чате."
            )

            return send_telegram_message(chat_id, message)

        except User.DoesNotExist:
            return send_telegram_message(
                chat_id,
                "Пользователь не найден. Пожалуйста, зарегистрируйтесь на сайте."
            )

    return send_telegram_message(
        chat_id,
        "Привет! Я бот для FileManager.\n\n"
        "Чтобы привязать ваш аккаунт, перейдите в профиль на сайте "
        "и следуйте инструкциям."
    )


def handle_link_command(chat_id, text):
    """Обработка команды /link"""
    parts = text.split()
    if len(parts) < 2:
        return send_telegram_message(
            chat_id,
            "Использование: /link <код_подтверждения>"
        )

    code = parts[1]
    user_id = cache.get(f"telegram_verify_{code}")

    if not user_id:
        return send_telegram_message(
            chat_id,
            "Неверный или устаревший код. Пожалуйста, получите новый код на сайте."
        )

    try:
        user = User.objects.get(id=user_id)
        user.profile.telegram_chat_id = chat_id
        user.profile.save()

        cache.delete(f"telegram_verify_{code}")

        return send_telegram_message(
            chat_id,
            f"Аккаунт успешно привязан! Вы будете получать уведомления о действиях."
        )

    except Exception as e:
        logger.error(f"Link account error: {str(e)}")
        return send_telegram_message(
            chat_id,
            "Произошла ошибка. Пожалуйста, попробуйте позже."
        )


def generate_verification_code(user_id):
    """Генерация кода подтверждения"""
    from django.core.cache import cache
    import secrets

    code = secrets.token_hex(3)
    cache.set(f"telegram_verify_{code}", user_id, timeout=3600)  # 1 час

    return code


def send_telegram_message(chat_id, text):
    """Отправка сообщения через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return JsonResponse({'status': 'error'}, status=500)


def setup_telegram_webhook():
    """Настройка вебхука для Telegram бота"""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        'url': settings.TELEGRAM_WEBHOOK_URL,
        'allowed_updates': ['message']
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info("Telegram webhook setup successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up Telegram webhook: {str(e)}")
        return False