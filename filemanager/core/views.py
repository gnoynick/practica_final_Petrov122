# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from .forms import FileUploadForm, FileReplaceForm
from .models import StoredFile
import os
from pathlib import Path
from ml_api.tasks import process_file_task


from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import StoredFile
from .serializers import FileSerializer


@login_required
def file_list(request):
    files = StoredFile.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'core/file_list.html', {'files': files})


@login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.save(commit=False)
            file.user = request.user
            file.save()

            # Start processing task
            process_file_task.delay(file.id, request.user.id)

            messages.success(request, 'Файл успешно загружен и отправлен на обработку')
            return redirect('file_list')
    else:
        form = FileUploadForm()
    return render(request, 'core/upload.html', {'form': form})


@login_required
def replace_file(request, pk):
    file = get_object_or_404(StoredFile, pk=pk, user=request.user)

    if request.method == 'POST':
        form = FileReplaceForm(request.POST, request.FILES, instance=file)
        if form.is_valid():
            # Delete old file
            if file.file and os.path.exists(file.file.path):
                os.remove(file.file.path)

            # Save new file
            file = form.save()
            file.processed = False
            file.processing_status = 'pending'
            file.save()

            # Start processing task
            process_file_task.delay(file.id, request.user.id)

            messages.success(request, 'Файл успешно заменен и отправлен на обработку')
            return redirect('file_list')
    else:
        form = FileReplaceForm(instance=file)

    return render(request, 'core/replace.html', {
        'form': form,
        'file': file
    })


@login_required
def delete_file(request, pk):
    file = get_object_or_404(StoredFile, pk=pk, user=request.user)
    if request.method == 'POST':
        file.delete()
        messages.success(request, 'Файл успешно удален')
    return redirect('file_list')


@login_required
def view_file(request, pk):
    file = get_object_or_404(StoredFile, pk=pk, user=request.user)
    return render(request, 'core/view_file.html', {'file': file})


@login_required
def download_file(request, pk):
    file = get_object_or_404(StoredFile, pk=pk, user=request.user)
    response = FileResponse(file.file.open('rb'), as_attachment=True, filename=file.filename())
    return response


def check_processing_status(request, pk):
    file = get_object_or_404(StoredFile, pk=pk, user=request.user)
    return JsonResponse({
        'processed': file.processed,
        'status': file.processing_status
    })

class FileViewSet(viewsets.ModelViewSet):
    queryset = StoredFile.objects.all()
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Возвращает только файлы текущего пользователя"""
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Привязывает файл к текущему пользователю при создании"""
        serializer.save(user=self.request.user)