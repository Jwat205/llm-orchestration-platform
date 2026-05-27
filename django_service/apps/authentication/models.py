from django.db import models
from django.conf import settings
import secrets

class APIKey(models.Model):
    key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['user', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(48)[:64]  # Random secure key
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.user.email}: {self.name or self.key[:8]}"
