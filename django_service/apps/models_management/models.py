# django-service/apps/models_management/models.py
from django.db import models

class ModelVersion(models.Model):
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    path = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class ModelPerformanceMetrics(models.Model):
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE)
    latency_ms = models.FloatField()
    throughput = models.FloatField()
    memory_mb = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

class ModelConfiguration(models.Model):
    model_version = models.OneToOneField(ModelVersion, on_delete=models.CASCADE)
    parameters = models.JSONField()
    quantized = models.BooleanField(default=False)
    format = models.CharField(max_length=20)

class DeploymentHistory(models.Model):
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE)
    deployed_by = models.CharField(max_length=100)
    deployed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

class ResourceUsage(models.Model):
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE)
    cpu_percent = models.FloatField()
    gpu_percent = models.FloatField(null=True, blank=True)
    memory_mb = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)