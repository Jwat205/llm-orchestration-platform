# django-service/apps/security/rbac.py
from django.core.cache import cache
from django.db.models import Q
from functools import wraps
from typing import List, Dict, Optional, Union
import logging
from datetime import timedelta
from django.utils import timezone

from .models import SecurityUser, Role, Permission, Organization, AuditLog

logger = logging.getLogger(__name__)

class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        
    def create_default_roles(self, organization: Organization) -> Dict[str, Role]:
        """Create default roles for a new organization"""
        default_roles = {
            'admin': {
                'name': 'Administrator',
                'role_type': 'admin',
                'description': 'Full system access and administration',
                'permissions': [
                    'api:admin', 'models:admin', 'billing:admin', 
                    'analytics:admin', 'users:admin', 'security:admin',
                    'training:admin', 'embedding:admin'
                ]
            },
            'developer': {
                'name': 'Developer',
                'role_type': 'developer',
                'description': 'API access and model management',
                'permissions': [
                    'api:execute', 'api:read', 'models:read', 'models:execute',
                    'analytics:read', 'training:create', 'training:read',
                    'embedding:execute', 'embedding:read'
                ]
            },
            'analyst': {
                'name': 'Analyst',
                'role_type': 'analyst',
                'description': 'Analytics and reporting access',
                'permissions': [
                    'api:read', 'analytics:read', 'analytics:create',
                    'models:read', 'billing:read'
                ]
            },
            'viewer': {
                'name': 'Viewer',
                'role_type': 'viewer',
                'description': 'Read-only access',
                'permissions': [
                    'api:read', 'models:read', 'analytics:read'
                ]
            }
        }
        
        created_roles = {}
        for role_key, role_data in default_roles.items():
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                organization=organization,
                defaults={
                    'role_type': role_data['role_type'],
                    'description': role_data['description']
                }
            )
            
            if created:
                # Assign permissions
                for perm_string in role_data['permissions']:
                    resource_type, action = perm_string.split(':')
                    try:
                        permission = Permission.objects.get(
                            resource_type=resource_type,
                            action=action
                        )
                        role.permissions.add(permission)
                    except Permission.DoesNotExist:
                        logger.warning(f"Permission {perm_string} not found")
                        
            created_roles[role_key] = role
            
        return created_roles
    
    def assign_role(self, user: SecurityUser, role: Role, assigned_by: SecurityUser = None) -> bool:
        """Assign role to user with audit logging"""
        try:
            if role.organization != user.organization:
                raise ValueError("Role and user must belong to same organization")
                
            user.roles.add(role)
            
            # Clear user permission cache
            self._clear_user_cache(user)
            
            # Audit log
            AuditLog.objects.create(
                organization=user.organization,
                user=assigned_by,
                action='permission_change',
                resource_type='user',
                resource_id=str(user.id),
                severity='medium',
                ip_address='127.0.0.1',  # Should be passed from request
                details={
                    'action': 'role_assigned',
                    'target_user': user.username,
                    'role': role.name,
                    'assigned_by': assigned_by.username if assigned_by else 'system'
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign role {role.name} to user {user.username}: {e}")
            return False
    
    def remove_role(self, user: SecurityUser, role: Role, removed_by: SecurityUser = None) -> bool:
        """Remove role from user with audit logging"""
        try:
            user.roles.remove(role)
            
            # Clear user permission cache
            self._clear_user_cache(user)
            
            # Audit log
            AuditLog.objects.create(
                organization=user.organization,
                user=removed_by,
                action='permission_change',
                resource_type='user',
                resource_id=str(user.id),
                severity='medium',
                ip_address='127.0.0.1',
                details={
                    'action': 'role_removed',
                    'target_user': user.username,
                    'role': role.name,
                    'removed_by': removed_by.username if removed_by else 'system'
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove role {role.name} from user {user.username}: {e}")
            return False
    
    def check_permission(self, user: SecurityUser, resource_type: str, action: str) -> bool:
        """Check if user has specific permission with caching"""
        cache_key = f"rbac_perm_{user.id}_{resource_type}_{action}"
        result = cache.get(cache_key)
        
        if result is None:
            result = user.has_permission(resource_type, action)
            cache.set(cache_key, result, self.cache_timeout)
            
        return result
    
    def get_user_permissions(self, user: SecurityUser) -> List[Dict]:
        """Get all permissions for a user"""
        cache_key = f"rbac_user_perms_{user.id}"
        permissions = cache.get(cache_key)
        
        if permissions is None:
            permissions = []
            user_permissions = Permission.objects.filter(
                roles__in=user.roles.all()
            ).distinct().select_related()
            
            for perm in user_permissions:
                permissions.append({
                    'resource_type': perm.resource_type,
                    'action': perm.action,
                    'name': perm.name,
                    'description': perm.description
                })
                
            cache.set(cache_key, permissions, self.cache_timeout)
            
        return permissions
    
    def get_role_hierarchy(self, organization: Organization) -> Dict:
        """Get role hierarchy for organization"""
        hierarchy = {
            'admin': 4,
            'security_admin': 3,
            'billing_admin': 3,
            'developer': 2,
            'analyst': 1,
            'viewer': 0
        }
        
        roles = Role.objects.filter(organization=organization)
        role_levels = {}
        
        for role in roles:
            role_levels[role.name] = hierarchy.get(role.role_type, 0)
            
        return role_levels
    
    def can_manage_user(self, manager: SecurityUser, target_user: SecurityUser) -> bool:
        """Check if manager can manage target user based on role hierarchy"""
        if manager.organization != target_user.organization:
            return False
            
        # Admin can manage anyone
        if manager.roles.filter(role_type='admin').exists():
            return True
            
        hierarchy = self.get_role_hierarchy(manager.organization)
        
        manager_level = max([hierarchy.get(role.name, 0) for role in manager.roles.all()] or [0])
        target_level = max([hierarchy.get(role.name, 0) for role in target_user.roles.all()] or [0])
        
        return manager_level > target_level
    
    def audit_permission_check(self, user: SecurityUser, resource_type: str, 
                             action: str, success: bool, ip_address: str,
                             request_id: str = None) -> None:
        """Audit permission checks for compliance"""
        # Only log high-privilege or failed checks to avoid spam
        if not success or resource_type in ['security', 'users', 'billing']:
            AuditLog.objects.create(
                organization=user.organization,
                user=user,
                action='security_event',
                resource_type=resource_type,
                severity='high' if not success else 'low',
                ip_address=ip_address,
                request_id=request_id,
                details={
                    'permission_check': True,
                    'requested_action': action,
                    'granted': success
                },
                success=success
            )
    
    def _clear_user_cache(self, user: SecurityUser) -> None:
        """Clear all cached data for a user"""
        # Clear permission caches
        cache_pattern = f"rbac_*_{user.id}_*"
        cache.delete_many([
            f"rbac_user_perms_{user.id}",
            f"user_perm_{user.id}_*"
        ])
        
        # Use wildcard delete if available
        try:
            cache.delete_pattern(f"*{user.id}*")
        except AttributeError:
            # Fallback for cache backends that don't support patterns
            pass

# Decorator for permission checking
def require_permission(resource_type: str, action: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Authentication required'}, status=401)
                
            rbac = RBACManager()
            if not rbac.check_permission(request.user, resource_type, action):
                # Audit failed permission check
                rbac.audit_permission_check(
                    request.user, resource_type, action, False, 
                    request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    request.META.get('HTTP_X_REQUEST_ID')
                )
                
                from django.http import JsonResponse
                return JsonResponse({'error': 'Insufficient permissions'}, status=403)
                
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

# Permission checking utilities
class PermissionChecker:
    """Utility class for permission checking"""
    
    @staticmethod
    def can_access_api(user: SecurityUser, endpoint: str = None) -> bool:
        """Check if user can access API endpoints"""
        rbac = RBACManager()
        
        # Basic API access
        if not rbac.check_permission(user, 'api', 'execute'):
            return False
            
        # Endpoint-specific checks
        if endpoint:
            if endpoint.startswith('/admin/') and not rbac.check_permission(user, 'api', 'admin'):
                return False
            elif endpoint.startswith('/billing/') and not rbac.check_permission(user, 'billing', 'read'):
                return False
            elif endpoint.startswith('/users/') and not rbac.check_permission(user, 'users', 'read'):
                return False
                
        return True
    
    @staticmethod
    def can_manage_models(user: SecurityUser, action: str = 'read') -> bool:
        """Check if user can manage ML models"""
        rbac = RBACManager()
        return rbac.check_permission(user, 'models', action)
    
    @staticmethod
    def can_access_analytics(user: SecurityUser, action: str = 'read') -> bool:
        """Check if user can access analytics"""
        rbac = RBACManager()
        return rbac.check_permission(user, 'analytics', action)
    
    @staticmethod
    def can_manage_billing(user: SecurityUser, action: str = 'read') -> bool:
        """Check if user can manage billing"""
        rbac = RBACManager()
        return rbac.check_permission(user, 'billing', action)
    
    @staticmethod
    def get_accessible_organizations(user: SecurityUser) -> List[Organization]:
        """Get organizations user has access to"""
        # For now, users only have access to their own organization
        # This can be extended for multi-org access
        return [user.organization] if user.organization else []

# Context manager for elevated permissions
class ElevatedPermissions:
    """Context manager for temporary permission elevation"""
    
    def __init__(self, user: SecurityUser, resource_type: str, action: str):
        self.user = user
        self.resource_type = resource_type
        self.action = action
        self.original_permissions = None
        
    def __enter__(self):
        # Store original permissions
        rbac = RBACManager()
        self.original_permissions = rbac.get_user_permissions(self.user)
        
        # This would require implementing temporary permission grants
        # For now, just log the elevation
        AuditLog.objects.create(
            organization=self.user.organization,
            user=self.user,
            action='permission_escalation',
            resource_type=self.resource_type,
            severity='high',
            ip_address='127.0.0.1',
            details={
                'temporary_elevation': True,
                'elevated_action': self.action,
                'context': 'automated_process'
            }
        )
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Log end of elevation
        AuditLog.objects.create(
            organization=self.user.organization,
            user=self.user,
            action='permission_escalation',
            resource_type=self.resource_type,
            severity='medium',
            ip_address='127.0.0.1',
            details={
                'temporary_elevation_ended': True,
                'duration': 'context_completed'
            }
        )