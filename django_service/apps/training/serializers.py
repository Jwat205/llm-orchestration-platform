# django-service/apps/training/serializers.py
from rest_framework import serializers
from .models import Dataset, HyperparameterConfig, TrainingJob

class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = '__all__'

class HyperparameterConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = HyperparameterConfig
        fields = '__all__'

class TrainingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingJob
        fields = '__all__'