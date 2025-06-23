from django.test import TestCase
from django.contrib.auth.models import User
from core.models import StoredFile
import tempfile
import os


class StoredFileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.file = StoredFile.objects.create(
            user=self.user,
            file='test.txt',
            description='Test file'
        )

    def test_file_creation(self):
        """Тест создания файла"""
        self.assertEqual(self.file.filename(), 'test.txt')
        self.assertEqual(str(self.file), 'test.txt')
        self.assertEqual(self.file.user.username, 'testuser')

    def test_file_deletion(self):
        """Тест удаления файла с файловой системы"""
        with tempfile.NamedTemporaryFile(dir='media/uploads', delete=False) as tmp:
            tmp.write(b'test content')
            self.file.file = tmp.name

        file_path = self.file.file.path
        self.assertTrue(os.path.exists(file_path))
        self.file.delete()
        self.assertFalse(os.path.exists(file_path))