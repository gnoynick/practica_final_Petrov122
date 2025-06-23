from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from core.models import StoredFile  # Изменено с .models

class FileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.force_authenticate(user=self.user)
        self.file = StoredFile.objects.create(
            user=self.user,
            file='test.txt',
            description='Test file'
        )

    def test_file_list_api(self):
        """Тест получения списка файлов через API"""
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_file_search(self):
        """Тест поиска по описанию"""
        response = self.client.get('/api/files/?search=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)