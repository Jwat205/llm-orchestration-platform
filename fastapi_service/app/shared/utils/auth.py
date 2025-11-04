import jwt
from functools import wraps
from fastapi import HTTPException, Request, status

SECRET_KEY = "your-secret"  # Load from env ideally

def parse_jwt(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def api_key_required(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != "expected_api_key":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return await func(request, *args, **kwargs)
    return wrapper

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(user_permissions: list, *args, **kwargs):
            if permission not in user_permissions:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Rate limiting can be implemented with decorators or dependencies in FastAPI
