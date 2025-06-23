from django import forms
from .models import StoredFile

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = StoredFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.txt,.png,.jpg,.jpeg,.xlsx,.csv'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Краткое описание файла'
            })
        }

class FileReplaceForm(forms.ModelForm):
    class Meta:
        model = StoredFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.txt,.png,.jpg,.jpeg,.xlsx,.csv'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Обновленное описание файла'
            })
        }
        labels = {
            'file': 'Новый файл',
            'description': 'Описание'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].required = True


class EmailForm(forms.Form):
    email = forms.EmailField(
        label='Email получателя',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@mail.ru'
        })
    )

    subject = forms.CharField(
        label='Тема письма',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: "Отчет о файле"'
        })
    )

    message = forms.CharField(
        label='Сообщение',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Введите текст сообщения...\n\nСсылка на файл будет добавлена автоматически'
        }),
        help_text='Вы можете вставить дополнительную информацию об отчете'
    )

    def __init__(self, *args, **kwargs):
        file_url = kwargs.pop('file_url', None)
        super().__init__(*args, **kwargs)

        if file_url:
            self.fields['message'].initial = f"Отчет по файлу:\n{file_url}\n\nДополнительные сведения:"