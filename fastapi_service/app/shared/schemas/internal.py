from pydantic import BaseModel, EmailStr
from typing import Optional

# Token validation request
class UserValidationRequest(BaseModel):
    token: str

# Token validation response
class UserValidationResponse(BaseModel):
    valid: bool
    user_id: Optional[int]
    email: Optional[EmailStr]
    is_active: Optional[bool]

# Usage logging request
class UsageLoggingRequest(BaseModel):
    user_id: int
    endpoint: str
    tokens_used: int
    cost: float

# Rate limit check request
class RateLimitCheckRequest(BaseModel):
    user_id: int
    api_key: Optional[str]

# Service health check request
class ServiceHealthRequest(BaseModel):
    service_name: str
