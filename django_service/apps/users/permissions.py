# apps/users/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission: only owners can edit, others can read.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.user == request.user

class IsSelf(BasePermission):
    """
    Only the user themselves can access/modify their own profile.
    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user
