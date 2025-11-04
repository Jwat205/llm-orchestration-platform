# django-service/apps/training/models.py
from django.db import models

class Dataset(models.Model):
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class HyperparameterConfig(models.Model):
    name = models.CharField(max_length=100)
    parameters = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class TrainingJob(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    hyperparams = models.ForeignKey(HyperparameterConfig, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metrics = models.JSONField(null=True, blank=True)