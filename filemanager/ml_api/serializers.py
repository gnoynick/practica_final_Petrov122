from rest_framework import serializers
from .models import MLRequest

class MLRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLRequest
        fields = '__all__'
        read_only_fields = ('user', 'created_at')