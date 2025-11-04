# fastapi-service/app/core/security.py
import httpx
from app.config import settings
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

async def validate_jwt_token(token: str):
    """
    Validate JWT token with Django service
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.DJANGO_AUTH_URL,
            headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 200:
            return resp.json()  # Should contain user info
    return None

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Optionally extract and validate JWT here for all endpoints
        # Or handle in dependencies.py as above
        response = await call_next(request)
        return response
