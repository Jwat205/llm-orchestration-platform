from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.security import validate_jwt_token
from ..core.django_client import django_client  # Add this import
from app.config import Settings, settings
from typing import Optional

auth_scheme = HTTPBearer(auto_error=False)  # Don't auto error for development

class DevUser:
    def __init__(self):
        self.user_id = "dev-user-123"
        self.username = "dev-user"
        self.valid = True
        self.permissions = ["chat", "embeddings", "documents"]

async def authenticate_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme)):
    # Development mode bypass
    if settings.ENV == "development" and settings.DEBUG:
        print("Development mode: bypassing authentication")
        return DevUser()

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")

    token = credentials.credentials# ✅ This is correct now
    print(f"Authenticating token: {token}")

    try:
        user_validation = await django_client.validate_token(token)
        if not user_validation or not user_validation.valid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return user_validation  # ✅ This is what downstream gets as 'user'
    except Exception as e:
        print(f"Auth error: {e}")
        if settings.ENV == "development":
            print("Falling back to development user")
            return DevUser()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

# Rate limiting via Django internal API — keep logic centralized there
async def check_rate_limit(user=Depends(authenticate_user)):
    allowed = await django_client.check_rate_limit(user.user_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    return True

# Log usage back to Django for billing/monitoring
async def log_usage(usage_data: dict):
    await django_client.log_usage(usage_data)

# Permission check wrapper
async def require_permissions(required_permission: str, user=Depends(authenticate_user)):
    if required_permission not in getattr(user, 'permissions', []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return True

def require_role(role: str):
    async def _check(user=Depends(authenticate_user)):
        user_permissions = getattr(user, 'permissions', [])
        if 'admin' in user_permissions or role in user_permissions:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {role} permission",
        )
    return _check
