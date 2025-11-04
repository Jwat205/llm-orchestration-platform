# django-service/apps/security/audit_logger.py
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue

from .models import AuditLog, SecurityEvent, SecurityUser, Organization

logger = logging.getLogger(__name__)

class AuditLogger:
    """Comprehensive audit logging system"""
    
    def __init__(self):
        self.log_queue = Queue()
        self.batch_size = getattr(settings, 'AUDIT_BATCH_SIZE', 100)
        self.flush_interval = getattr(settings, 'AUDIT_FLUSH_INTERVAL', 30)  # seconds
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._setup_background_processing()
        
    def _setup_background_processing(self):
        """Setup background thread for batch processing"""
        def background_processor():
            while True:
                try:
                    logs_to_process = []
                    
                    # Collect logs for batch processing
                    while len(logs_to_process) < self.batch_size:
                        try:
                            log_entry = self.log_queue.get(timeout=self.flush_interval)
                            logs_to_process.append(log_entry)
                        except:
                            break  # Timeout or empty queue
                    
                    if logs_to_process:
                        self._batch_create_logs(logs_to_process)
                        
                except Exception as e:
                    logger.error(f"Background audit processing error: {e}")
        
        # Start background thread
        thread = threading.Thread(target=background_processor, daemon=True)
        thread.start()
    
    def log_event(self, organization: Organization, user: Optional[SecurityUser] = None,
                  action: str = '', resource_type: str = '', resource_id: str = '',
                  severity: str = 'low', ip_address: str = '127.0.0.1',
                  user_agent: str = '', request_id: str = '', details: Dict = None,
                  success: bool = True, error_message: str = '') -> None:
        """Log audit event (async via queue)"""
        
        log_entry = {
            'organization_id': organization.id,
            'user_id': user.id if user else None,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'severity': severity,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_id': request_id,
            'details': details or {},
            'success': success,
            'error_message': error_message,
            'timestamp': timezone.now()
        }
        
        # Add to queue for batch processing
        try:
            self.log_queue.put_nowait(log_entry)
        except:
            # Queue full, process synchronously
            self._create_audit_log(log_entry)
    
    def log_sync(self, organization: Organization, user: Optional[SecurityUser] = None,
                 action: str = '', resource_type: str = '', resource_id: str = '',
                 severity: str = 'low', ip_address: str = '127.0.0.1',
                 user_agent: str = '', request_id: str = '', details: Dict = None,
                 success: bool = True, error_message: str = '') -> AuditLog:
        """Log audit event synchronously"""
        
        log_entry = {
            'organization_id': organization.id,
            'user_id': user.id if user else None,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'severity': severity,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_id': request_id,
            'details': details or {},
            'success': success,
            'error_message': error_message,
            'timestamp': timezone.now()
        }
        
        return self._create_audit_log(log_entry)
    
    def _batch_create_logs(self, log_entries: List[Dict]) -> None:
        """Create multiple audit logs in batch"""
        try:
            with transaction.atomic():
                audit_logs = []
                for entry in log_entries:
                    audit_log = AuditLog(
                        organization_id=entry['organization_id'],
                        user_id=entry['user_id'],
                        action=entry['action'],
                        resource_type=entry['resource_type'],
                        resource_id=entry['resource_id'],
                        severity=entry['severity'],
                        ip_address=entry['ip_address'],
                        user_agent=entry['user_agent'],
                        request_id=entry['request_id'],
                        details=entry['details'],
                        success=entry['success'],
                        error_message=entry['error_message'],
                        timestamp=entry['timestamp']
                    )
                    audit_logs.append(audit_log)
                
                AuditLog.objects.bulk_create(audit_logs, batch_size=100)
                logger.debug(f"Batch created {len(audit_logs)} audit logs")
                
        except Exception as e:
            logger.error(f"Batch audit log creation failed: {e}")
            # Fallback to individual creation
            for entry in log_entries:
                try:
                    self._create_audit_log(entry)
                except Exception as individual_error:
                    logger.error(f"Individual audit log creation failed: {individual_error}")
    
    def _create_audit_log(self, entry: Dict) -> AuditLog:
        """Create single audit log"""
        try:
            return AuditLog.objects.create(
                organization_id=entry['organization_id'],
                user_id=entry['user_id'],
                action=entry['action'],
                resource_type=entry['resource_type'],
                resource_id=entry['resource_id'],
                severity=entry['severity'],
                ip_address=entry['ip_address'],
                user_agent=entry['user_agent'],
                request_id=entry['request_id'],
                details=entry['details'],
                success=entry['success'],
                error_message=entry['error_message'],
                timestamp=entry['timestamp']
            )
        except Exception as e:
            logger.error(f"Audit log creation failed: {e}")
            raise

class SecurityEventLogger:
    """Security event logging and incident management"""
    
    def __init__(self):
        self.risk_scores = {
            'failed_login': 10,
            'account_locked': 25,
            'suspicious_activity': 50,
            'permission_escalation': 75,
            'data_breach_attempt': 90,
            'malicious_request': 60,
            'rate_limit_exceeded': 20,
            'unauthorized_access': 70,
            'vulnerability_detected': 80
        }
    
    def log_security_event(self, organization: Organization, event_type: str,
                          severity: str, user: Optional[SecurityUser] = None,
                          ip_address: str = '127.0.0.1', description: str = '',
                          details: Dict = None) -> SecurityEvent:
        """Log security event with automatic risk scoring"""
        
        risk_score = self.risk_scores.get(event_type, 50)
        
        # Adjust risk score based on factors
        if user and self._is_privileged_user(user):
            risk_score += 20
            
        if self._is_suspicious_ip(ip_address, organization):
            risk_score += 15
            
        if self._is_repeated_event(event_type, ip_address, organization):
            risk_score += 25
        
        # Cap at 100
        risk_score = min(risk_score, 100)
        
        # Create security event
        event = SecurityEvent.objects.create(
            organization=organization,
            event_type=event_type,
            severity=severity,
            user=user,
            ip_address=ip_address,
            description=description,
            details=details or {},
            risk_score=risk_score
        )
        
        # Trigger automated response if high risk
        if risk_score >= 70:
            self._trigger_automated_response(event)
        
        # Alert if critical
        if severity == 'critical' or risk_score >= 90:
            self._send_security_alert(event)
        
        return event
    
    def _is_privileged_user(self, user: SecurityUser) -> bool:
        """Check if user has privileged roles"""
        privileged_roles = ['admin', 'security_admin', 'billing_admin']
        return user.roles.filter(role_type__in=privileged_roles).exists()
    
    def _is_suspicious_ip(self, ip_address: str, organization: Organization) -> bool:
        """Check if IP is suspicious based on history"""
        cache_key = f"suspicious_ip_{ip_address}"
        result = cache.get(cache_key)
        
        if result is None:
            # Check recent failed events from this IP
            recent_failures = SecurityEvent.objects.filter(
                organization=organization,
                ip_address=ip_address,
                success=False,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            result = recent_failures >= 5
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
        
        return result
    
    def _is_repeated_event(self, event_type: str, ip_address: str, 
                          organization: Organization) -> bool:
        """Check if this is a repeated event from same IP"""
        recent_count = SecurityEvent.objects.filter(
            organization=organization,
            event_type=event_type,
            ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        return recent_count >= 3
    
    def _trigger_automated_response(self, event: SecurityEvent) -> None:
        """Trigger automated security response"""
        responses = []
        
        # Rate limiting
        if event.event_type in ['rate_limit_exceeded', 'malicious_request']:
            self._apply_ip_rate_limit(event.ip_address, event.organization)
            responses.append('ip_rate_limited')
        
        # Account locking
        if event.event_type == 'failed_login' and event.user:
            failed_attempts = SecurityEvent.objects.filter(
                organization=event.organization,
                user=event.user,
                event_type='failed_login',
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if failed_attempts >= 5:
                event.user.failed_login_attempts = failed_attempts
                event.user.locked_until = timezone.now() + timedelta(hours=1)
                event.user.save()
                responses.append('account_locked')
        
        # IP blocking for severe events
        if event.risk_score >= 90:
            self._block_ip_temporarily(event.ip_address, event.organization)
            responses.append('ip_blocked')
        
        # Update event with automated responses
        event.automated_response = {
            'responses': responses,
            'timestamp': timezone.now().isoformat()
        }
        event.save()
    
    def _apply_ip_rate_limit(self, ip_address: str, organization: Organization) -> None:
        """Apply aggressive rate limiting to IP"""
        cache_key = f"rate_limit_{organization.id}_{ip_address}"
        cache.set(cache_key, 1, 3600)  # Block for 1 hour
        
        logger.warning(f"Applied rate limiting to IP {ip_address} for org {organization.name}")
    
    def _block_ip_temporarily(self, ip_address: str, organization: Organization) -> None:
        """Temporarily block IP address"""
        cache_key = f"blocked_ip_{organization.id}_{ip_address}"
        cache.set(cache_key, True, 7200)  # Block for 2 hours
        
        logger.critical(f"Temporarily blocked IP {ip_address} for org {organization.name}")
    
    def _send_security_alert(self, event: SecurityEvent) -> None:
        """Send security alert to administrators"""
        try:
            # Get security administrators
            security_admins = SecurityUser.objects.filter(
                organization=event.organization,
                roles__role_type__in=['admin', 'security_admin'],
                is_active=True
            ).distinct()
            
            alert_message = {
                'event_id': str(event.id),
                'event_type': event.event_type,
                'severity': event.severity,
                'risk_score': event.risk_score,
                'ip_address': event.ip_address,
                'description': event.description,
                'timestamp': event.created_at.isoformat(),
                'user': event.user.username if event.user else 'Unknown'
            }
            
            # Queue alert for sending (implement actual notification system)
            cache.set(f"security_alert_{event.id}", alert_message, 86400)
            
            logger.critical(f"Security alert generated: {alert_message}")
            
        except Exception as e:
            logger.error(f"Failed to send security alert: {e}")

class ComplianceLogger:
    """Compliance-specific logging for SOC2, GDPR, etc."""
    
    def __init__(self):
        self.compliance_events = {
            'data_access': ['read', 'export', 'download'],
            'data_modification': ['create', 'update', 'delete'],
            'user_management': ['user_created', 'user_updated', 'user_deleted', 'permission_change'],
            'system_changes': ['configuration_change', 'security_setting_change'],
            'authentication': ['login', 'logout', 'failed_login', 'password_change']
        }
    
    def log_compliance_event(self, organization: Organization, category: str,
                           action: str, user: Optional[SecurityUser] = None,
                           resource_type: str = '', resource_id: str = '',
                           ip_address: str = '127.0.0.1', details: Dict = None) -> None:
        """Log compliance-relevant events"""
        
        compliance_details = {
            'category': category,
            'compliance_frameworks': self._get_applicable_frameworks(category, action),
            'retention_period': self._get_retention_period(category),
            'data_classification': self._classify_data_sensitivity(resource_type),
            **(details or {})
        }
        
        # Create audit log with compliance metadata
        audit_logger = AuditLogger()
        audit_logger.log_sync(
            organization=organization,
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            severity=self._get_compliance_severity(category, action),
            ip_address=ip_address,
            details=compliance_details
        )
        
        # GDPR-specific logging
        if 'gdpr' in compliance_details['compliance_frameworks']:
            self._log_gdpr_event(organization, action, user, resource_type, details)
    
    def _get_applicable_frameworks(self, category: str, action: str) -> List[str]:
        """Determine which compliance frameworks apply"""
        frameworks = []
        
        # SOC2 applies to most security events
        if category in ['authentication', 'user_management', 'system_changes']:
            frameworks.append('soc2')
        
        # GDPR applies to personal data events
        if category in ['data_access', 'data_modification']:
            frameworks.append('gdpr')
        
        # PCI DSS for payment data
        if 'payment' in action.lower() or 'billing' in action.lower():
            frameworks.append('pci_dss')
        
        return frameworks
    
    def _get_retention_period(self, category: str) -> int:
        """Get data retention period in days"""
        retention_periods = {
            'authentication': 2555,  # 7 years for SOC2
            'data_access': 2555,     # 7 years for GDPR
            'user_management': 2555, # 7 years for SOC2
            'system_changes': 2555,  # 7 years for SOC2
            'data_modification': 2190 # 6 years for GDPR
        }
        return retention_periods.get(category, 2555)  # Default 7 years
    
    def _classify_data_sensitivity(self, resource_type: str) -> str:
        """Classify data sensitivity level"""
        sensitive_resources = {
            'users': 'pii',
            'billing': 'financial',
            'models': 'proprietary',
            'api_keys': 'secret',
            'security': 'confidential'
        }
        return sensitive_resources.get(resource_type, 'internal')
    
    def _get_compliance_severity(self, category: str, action: str) -> str:
        """Determine severity for compliance purposes"""
        high_severity_actions = ['delete', 'export', 'permission_escalation', 'failed_login']
        medium_severity_categories = ['user_management', 'system_changes']
        
        if any(severity_action in action.lower() for severity_action in high_severity_actions):
            return 'high'
        elif category in medium_severity_categories:
            return 'medium'
        else:
            return 'low'
    
    def _log_gdpr_event(self, organization: Organization, action: str,
                       user: Optional[SecurityUser], resource_type: str,
                       details: Dict) -> None:
        """Additional GDPR-specific logging"""
        gdpr_details = {
            'lawful_basis': self._determine_lawful_basis(action, resource_type),
            'data_subject_rights': self._check_data_subject_rights(action),
            'cross_border_transfer': False,  # Set based on actual data flow
            'automated_decision_making': 'llm_inference' in action.lower()
        }
        
        # Store GDPR-specific metadata
        cache_key = f"gdpr_event_{organization.id}_{timezone.now().strftime('%Y%m%d')}"
        existing_events = cache.get(cache_key, [])
        existing_events.append({
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'user': user.username if user else 'system',
            'resource_type': resource_type,
            'gdpr_details': gdpr_details
        })
        cache.set(cache_key, existing_events, 86400)  # Store for 24 hours
    
    def _determine_lawful_basis(self, action: str, resource_type: str) -> str:
        """Determine GDPR lawful basis for processing"""
        if 'billing' in resource_type:
            return 'contract'
        elif 'analytics' in action:
            return 'legitimate_interest'
        elif 'security' in resource_type:
            return 'legitimate_interest'
        else:
            return 'consent'
    
    def _check_data_subject_rights(self, action: str) -> List[str]:
        """Check which data subject rights are relevant"""
        rights = []
        
        if 'read' in action or 'export' in action:
            rights.append('access')
        if 'update' in action:
            rights.append('rectification')
        if 'delete' in action:
            rights.append('erasure')
        if 'analytics' in action:
            rights.extend(['object', 'restrict_processing'])
            
        return rights

class AuditReportGenerator:
    """Generate audit reports for compliance"""
    
    def __init__(self):
        self.report_formats = ['json', 'csv', 'pdf']
    
    def generate_compliance_report(self, organization: Organization,
                                 start_date: datetime, end_date: datetime,
                                 compliance_framework: str = 'soc2') -> Dict:
        """Generate compliance report"""
        
        # Get relevant audit logs
        audit_logs = AuditLog.objects.filter(
            organization=organization,
            timestamp__range=(start_date, end_date)
        ).select_related('user')
        
        # Filter by compliance framework
        if compliance_framework:
            audit_logs = audit_logs.filter(
                details__compliance_frameworks__contains=[compliance_framework]
            )
        
        report_data = {
            'organization': organization.name,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'compliance_framework': compliance_framework,
            'total_events': audit_logs.count(),
            'summary': self._generate_summary(audit_logs),
            'events_by_category': self._categorize_events(audit_logs),
            'security_incidents': self._get_security_incidents(organization, start_date, end_date),
            'user_access_patterns': self._analyze_user_access(audit_logs),
            'failed_access_attempts': self._get_failed_attempts(audit_logs),
            'data_access_logs': self._get_data_access_logs(audit_logs),
            'system_changes': self._get_system_changes(audit_logs),
            'generated_at': timezone.now().isoformat()
        }
        
        return report_data
    
    def _generate_summary(self, audit_logs) -> Dict:
        """Generate summary statistics"""
        total_events = audit_logs.count()
        failed_events = audit_logs.filter(success=False).count()
        
        severity_counts = {}
        for severity in ['low', 'medium', 'high', 'critical']:
            severity_counts[severity] = audit_logs.filter(severity=severity).count()
        
        return {
            'total_events': total_events,
            'successful_events': total_events - failed_events,
            'failed_events': failed_events,
            'success_rate': (total_events - failed_events) / total_events * 100 if total_events > 0 else 0,
            'severity_breakdown': severity_counts
        }
    
    def _categorize_events(self, audit_logs) -> Dict:
        """Categorize events by type"""
        categories = {}
        
        for log in audit_logs:
            category = log.details.get('category', log.action)
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
            
        return categories
    
    def _get_security_incidents(self, organization: Organization,
                              start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get security incidents for the period"""
        incidents = SecurityEvent.objects.filter(
            organization=organization,
            created_at__range=(start_date, end_date),
            severity__in=['high', 'critical']
        ).order_by('-created_at')
        
        return [{
            'id': str(incident.id),
            'type': incident.event_type,
            'severity': incident.severity,
            'risk_score': incident.risk_score,
            'status': incident.status,
            'created_at': incident.created_at.isoformat(),
            'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None
        } for incident in incidents[:100]]  # Limit to 100 most recent
    
    def _analyze_user_access(self, audit_logs) -> Dict:
        """Analyze user access patterns"""
        user_access = {}
        
        for log in audit_logs.filter(user__isnull=False):
            username = log.user.username
            if username not in user_access:
                user_access[username] = {
                    'total_events': 0,
                    'successful_events': 0,
                    'failed_events': 0,
                    'last_activity': None,
                    'resources_accessed': set()
                }
            
            user_access[username]['total_events'] += 1
            if log.success:
                user_access[username]['successful_events'] += 1
            else:
                user_access[username]['failed_events'] += 1
                
            if not user_access[username]['last_activity'] or log.timestamp > user_access[username]['last_activity']:
                user_access[username]['last_activity'] = log.timestamp
                
            if log.resource_type:
                user_access[username]['resources_accessed'].add(log.resource_type)
        
        # Convert sets to lists for JSON serialization
        for username in user_access:
            user_access[username]['resources_accessed'] = list(user_access[username]['resources_accessed'])
            if user_access[username]['last_activity']:
                user_access[username]['last_activity'] = user_access[username]['last_activity'].isoformat()
        
        return user_access
    
    def _get_failed_attempts(self, audit_logs) -> List[Dict]:
        """Get failed access attempts"""
        failed_logs = audit_logs.filter(success=False).order_by('-timestamp')[:50]
        
        return [{
            'timestamp': log.timestamp.isoformat(),
            'user': log.user.username if log.user else 'Unknown',
            'action': log.action,
            'resource_type': log.resource_type,
            'ip_address': log.ip_address,
            'error_message': log.error_message
        } for log in failed_logs]
    
    def _get_data_access_logs(self, audit_logs) -> List[Dict]:
        """Get data access logs for compliance"""
        data_actions = ['read', 'export', 'download', 'create', 'update', 'delete']
        data_logs = audit_logs.filter(action__in=data_actions).order_by('-timestamp')[:100]
        
        return [{
            'timestamp': log.timestamp.isoformat(),
            'user': log.user.username if log.user else 'System',
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'data_classification': log.details.get('data_classification', 'unknown'),
            'lawful_basis': log.details.get('gdpr_details', {}).get('lawful_basis', 'not_applicable')
        } for log in data_logs]
    
    def _get_system_changes(self, audit_logs) -> List[Dict]:
        """Get system configuration changes"""
        system_actions = ['configuration_change', 'security_setting_change', 'permission_change']
        system_logs = audit_logs.filter(action__in=system_actions).order_by('-timestamp')
        
        return [{
            'timestamp': log.timestamp.isoformat(),
            'user': log.user.username if log.user else 'System',
            'action': log.action,
            'resource_type': log.resource_type,
            'details': log.details,
            'severity': log.severity
        } for log in system_logs]

# Global instances
audit_logger = AuditLogger()
security_event_logger = SecurityEventLogger()
compliance_logger = ComplianceLogger()
report_generator = AuditReportGenerator()

# Middleware for automatic audit logging
class AuditMiddleware:
    """Middleware to automatically log API requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.sensitive_endpoints = ['/admin/', '/api/v1/users/', '/api/v1/billing/', '/api/v1/security/']
        
    def __call__(self, request):
        start_time = timezone.now()
        
        # Process request
        response = self.get_response(request)
        
        # Log API calls for authenticated users
        if (request.user.is_authenticated and 
            hasattr(request.user, 'organization') and
            request.path.startswith('/api/')):
            
            # Determine if this should be logged
            should_log = (
                not response.status_code == 200 or  # Log all non-200 responses
                any(endpoint in request.path for endpoint in self.sensitive_endpoints) or  # Log sensitive endpoints
                request.method in ['POST', 'PUT', 'DELETE', 'PATCH']  # Log write operations
            )
            
            if should_log:
                processing_time = (timezone.now() - start_time).total_seconds()
                
                audit_logger.log_event(
                    organization=request.user.organization,
                    user=request.user,
                    action='api_call',
                    resource_type='api',
                    resource_id=request.path,
                    severity='low' if response.status_code < 400 else 'medium',
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_id=request.META.get('HTTP_X_REQUEST_ID'),
                    details={
                        'method': request.method,
                        'path': request.path,
                        'status_code': response.status_code,
                        'processing_time_seconds': processing_time,
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'referer': request.META.get('HTTP_REFERER', '')
                    },
                    success=response.status_code < 400
                )
        
        return response