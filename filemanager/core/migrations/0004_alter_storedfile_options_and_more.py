# Generated by Django 5.2.3 on 2025-06-21 10:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_storedfile_user'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='storedfile',
            options={'ordering': ['-uploaded_at'], 'verbose_name': 'Файл', 'verbose_name_plural': 'Файлы'},
        ),
        migrations.AlterField(
            model_name='storedfile',
            name='description',
            field=models.CharField(blank=True, max_length=100, verbose_name='Описание'),
        ),
        migrations.AlterField(
            model_name='storedfile',
            name='file',
            field=models.FileField(upload_to='uploads/%Y/%m/%d/', verbose_name='Файл'),
        ),
        migrations.AlterField(
            model_name='storedfile',
            name='uploaded_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки'),
        ),
        migrations.AlterField(
            model_name='storedfile',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
        ),
    ]
