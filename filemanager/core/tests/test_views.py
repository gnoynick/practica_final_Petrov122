import tempfile
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from core.models import StoredFile
from unittest.mock import patch
from django.core import mail


class FileUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_authenticated_file_upload(self):
        """Тест загрузки файла авторизованным пользователем"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
            tmp.write(b'test content')
            tmp.seek(0)
            response = self.client.post(reverse('upload_file'), {'file': tmp})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(StoredFile.objects.count(), 1)
        self.assertEqual(StoredFile.objects.first().user, self.user)

    def test_anonymous_file_upload(self):
        """Тест загрузки файла анонимным пользователем"""
        self.client.logout()
        with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
            response = self.client.post(reverse('upload_file'), {'file': tmp})

        self.assertEqual(response.status_code, 302)  # Должен перенаправить на страницу входа
        self.assertEqual(StoredFile.objects.count(), 0)

class EmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    @patch('core.views.send_mail')
    def test_send_report_email(self, mock_send_mail):
        """Тест отправки отчета с моккингом"""
        mock_send_mail.return_value = 1
        response = self.client.post(
            reverse('send_report') + '?file_url=http://test.com/file.txt',
            {'email': 'test@example.com', 'subject': 'Test', 'message': 'Hello'}
        )
        self.assertEqual(response.status_code, 200)
        mock_send_mail.assert_called_once()

    def test_real_email_sending(self):
        """Тест реальной отправки email (использует тестовый бэкенд)"""
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                reverse('send_report') + '?file_url=http://test.com/file.txt',
                {'email': 'test@example.com', 'subject': 'Test', 'message': 'Hello'}
            )
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].subject, 'Test')