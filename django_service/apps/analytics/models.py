from django.db import models
from django.conf import settings

class APIUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    endpoint = models.CharField(max_length=255)
    tokens_used = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

class UserQuota(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_limit = models.PositiveIntegerField(default=1000)
    tokens_limit = models.PositiveIntegerField(default=100000)
    tokens_used = models.PositiveIntegerField(default=0)
    requests_made = models.PositiveIntegerField(default=0)
    reset_date = models.DateTimeField()

class ModelUsage(models.Model):
    model_name = models.CharField(max_length=255)
    requests = models.PositiveIntegerField(default=0)
    avg_latency_ms = models.FloatField(default=0.0)
    last_used = models.DateTimeField(auto_now=True)
