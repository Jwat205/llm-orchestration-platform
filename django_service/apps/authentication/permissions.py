# apps/authentication/permissions.py

from rest_framework.permissions import BasePermission

class IsEmailVerified(BasePermission):
    """
    Allows access only to users with a verified email.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "is_email_verified", False)

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff
