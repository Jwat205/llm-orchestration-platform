# django-service/apps/security/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.core.cache import cache
import uuid
import hashlib
from datetime import timedelta

class Organization(models.Model):
    """Organization model for multi-tenancy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True)
    sso_enabled = models.BooleanField(default=False)
    sso_provider = models.CharField(max_length=50, blank=True)
    sso_metadata = JSONField(default=dict, blank=True)
    security_settings = JSONField(default=dict, blank=True)
    ip_whitelist = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def is_ip_allowed(self, ip_address):
        """Check if IP is whitelisted for this organization"""
        if not self.ip_whitelist:
            return True
        return ip_address in self.ip_whitelist

class Role(models.Model):
    """Role-based access control roles"""
    ROLE_TYPES = [
        ('admin', 'Administrator'),
        ('developer', 'Developer'),
        ('analyst', 'Analyst'),
        ('viewer', 'Viewer'),
        ('billing_admin', 'Billing Administrator'),
        ('security_admin', 'Security Administrator'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'organization']
    
    def __str__(self):
        return f"{self.organization.name} - {self.name}"

class Permission(models.Model):
    """Granular permissions for RBAC"""
    RESOURCE_TYPES = [
        ('api', 'API Access'),
        ('models', 'Model Management'),
        ('billing', 'Billing'),
        ('analytics', 'Analytics'),
        ('users', 'User Management'),
        ('security', 'Security Settings'),
        ('training', 'Model Training'),
        ('embedding', 'Embeddings'),
    ]
    
    ACTION_TYPES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('execute', 'Execute'),
        ('admin', 'Administrate'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField(blank=True)
    roles = models.ManyToManyField(Role, related_name='permissions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['resource_type', 'action']
    
    def __str__(self):
        return f"{self.resource_type}:{self.action}"

class SecurityUser(AbstractUser):
    """Extended user model with security features"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users')
    roles = models.ManyToManyField(Role, related_name='users', blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True)
    last_password_change = models.DateTimeField(default=timezone.now)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    sso_user_id = models.CharField(max_length=255, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
    security_settings = JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def has_permission(self, resource_type, action):
        """Check if user has specific permission"""
        cache_key = f"user_perm_{self.id}_{resource_type}_{action}"
        result = cache.get(cache_key)
        
        if result is None:
            result = Permission.objects.filter(
                roles__in=self.roles.all(),
                resource_type=resource_type,
                action=action
            ).exists()
            cache.set(cache_key, result, 300)  # Cache for 5 minutes
        
        return result
    
    def is_locked(self):
        """Check if account is locked due to failed attempts"""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
    
    def reset_failed_attempts(self):
        """Reset failed login attempts"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

class APIKey(models.Model):
    """API key management with rotation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(SecurityUser, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=8)
    permissions = models.ManyToManyField(Permission, blank=True)
    rate_limit = models.IntegerField(default=1000)  # requests per hour
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @classmethod
    def generate_key(cls):
        """Generate new API key"""
        key = f"sk-{uuid.uuid4().hex}"
        prefix = key[:8]
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key, prefix, key_hash
    
    def is_valid(self):
        """Check if API key is valid"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
    
    def record_usage(self):
        """Record API key usage"""
        self.last_used = timezone.now()
        self.usage_count += 1
        self.save(update_fields=['last_used', 'usage_count'])

class AuditLog(models.Model):
    """Comprehensive audit logging"""
    ACTION_TYPES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('api_call', 'API Call'),
        ('permission_change', 'Permission Change'),
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('api_key_created', 'API Key Created'),
        ('api_key_rotated', 'API Key Rotated'),
        ('api_key_deleted', 'API Key Deleted'),
        ('model_access', 'Model Access'),
        ('data_export', 'Data Export'),
        ('security_event', 'Security Event'),
        ('compliance_check', 'Compliance Check'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(SecurityUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    resource_type = models.CharField(max_length=50, blank=True)
    resource_id = models.CharField(max_length=255, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='low')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    details = JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['organization', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"

class SecurityEvent(models.Model):
    """Security events and incidents"""
    EVENT_TYPES = [
        ('failed_login', 'Failed Login'),
        ('account_locked', 'Account Locked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('permission_escalation', 'Permission Escalation'),
        ('data_breach_attempt', 'Data Breach Attempt'),
        ('malicious_request', 'Malicious Request'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('vulnerability_detected', 'Vulnerability Detected'),
    ]
    
    STATUS_TYPES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='security_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=AuditLog.SEVERITY_LEVELS)
    status = models.CharField(max_length=20, choices=STATUS_TYPES, default='open')
    user = models.ForeignKey(SecurityUser, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    description = models.TextField()
    details = JSONField(default=dict, blank=True)
    risk_score = models.IntegerField(default=0)  # 0-100
    automated_response = JSONField(default=dict, blank=True)
    resolved_by = models.ForeignKey(SecurityUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_events')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
        ]

class ComplianceReport(models.Model):
    """Compliance reporting for SOC2, GDPR, etc."""
    REPORT_TYPES = [
        ('soc2', 'SOC 2'),
        ('gdpr', 'GDPR'),
        ('hipaa', 'HIPAA'),
        ('pci_dss', 'PCI DSS'),
        ('iso27001', 'ISO 27001'),
        ('custom', 'Custom'),
    ]
    
    STATUS_TYPES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='compliance_reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_TYPES, default='generating')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    generated_by = models.ForeignKey(SecurityUser, on_delete=models.SET_NULL, null=True)
    report_data = JSONField(default=dict, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    compliance_score = models.FloatField(null=True, blank=True)
    findings = JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']