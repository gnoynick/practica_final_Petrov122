from rest_framework import serializers
from .models import StoredFile

class FileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_at = serializers.DateTimeField(format='%d.%m.%Y %H:%M')

    class Meta:
        model = StoredFile
        fields = '__all__'
        read_only_fields = ('user', 'uploaded_at')

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None