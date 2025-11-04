"""
Common API Components
Shared utilities, middleware, and components used across API versions
"""

from .middleware import VersionMiddleware, DeprecationMiddleware, RateLimitMiddleware
from .dependencies import get_api_version, validate_request, get_rate_limiter
from .responses import create_error_response, create_success_response
from .auth import get_current_user, verify_api_key
from .validation import validate_model_access, validate_request_size

__all__ = [
    "VersionMiddleware",
    "DeprecationMiddleware", 
    "RateLimitMiddleware",
    "get_api_version",
    "validate_request",
    "get_rate_limiter",
    "create_error_response",
    "create_success_response",
    "get_current_user",
    "verify_api_key",
    "validate_model_access",
    "validate_request_size"
]