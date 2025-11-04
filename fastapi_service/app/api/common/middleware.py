"""
Common Middleware Components
Shared middleware for version management, deprecation warnings, and rate limiting
"""

import time
import json
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from ...shared.versioning.version_manager import VersionManager
from ...shared.versioning.deprecation import DeprecationManager
from ...shared.versioning.compatibility import CompatibilityManager

logger = logging.getLogger(__name__)


class VersionMiddleware(BaseHTTPMiddleware):
    """Middleware for API version resolution and routing"""
    
    def __init__(self, app, version_manager: VersionManager = None):
        super().__init__(app)
        self.version_manager = version_manager or VersionManager()
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            # Resolve API version from request
            api_version = self.version_manager.resolve_api_version(
                request_path=str(request.url.path),
                headers=dict(request.headers),
                query_params=dict(request.query_params)
            )
            
            # Add version info to request state
            request.state.api_version = api_version.version if api_version else "1.0.0"
            request.state.version_source = "default"
            
            # Process request
            response = await call_next(request)
            
            # Add version headers to response
            if api_version:
                response.headers["X-API-Version"] = api_version.version
                response.headers["X-API-Version-Status"] = api_version.status.value
                
                # Add deprecation info if applicable
                if api_version.status.value == "deprecated":
                    response.headers["Deprecation"] = "true"
                    if api_version.sunset_date:
                        response.headers["Sunset"] = api_version.sunset_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
            
            # Add processing time
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Version middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Version resolution failed", "message": str(e)}
            )


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware for handling API deprecation warnings"""
    
    def __init__(self, app, deprecation_manager: DeprecationManager = None):
        super().__init__(app)
        self.deprecation_manager = deprecation_manager or DeprecationManager()
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Check for deprecation warnings
            api_version = getattr(request.state, 'api_version', '1.0.0')
            endpoint_path = str(request.url.path)
            
            # Get deprecation warnings
            warnings = self.deprecation_manager.get_deprecation_warnings(
                api_version=api_version,
                endpoint=endpoint_path
            )
            
            # Record usage if deprecated features are used
            for warning in warnings:
                client_id = self._extract_client_id(request)
                user_agent = request.headers.get("User-Agent", "unknown")
                
                self.deprecation_manager.record_deprecation_usage(
                    warning.notice_id,
                    client_id=client_id,
                    endpoint=endpoint_path,
                    user_agent=user_agent
                )
            
            # Process request
            response = await call_next(request)
            
            # Add deprecation headers if warnings exist
            if warnings:
                headers = self.deprecation_manager.get_deprecation_headers(warnings)
                for key, value in headers.items():
                    response.headers[key] = value
                
                # Add deprecation data to response if JSON
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        # This is a simplified approach - in production you'd want more sophisticated response modification
                        deprecation_data = self.deprecation_manager.get_deprecation_response_data(warnings)
                        response.headers["X-Deprecation-Count"] = str(len(warnings))
                        response.headers["X-Deprecation-Info"] = json.dumps(deprecation_data)
                    except Exception as e:
                        logger.warning(f"Failed to add deprecation data to response: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"Deprecation middleware error: {e}")
            return await call_next(request)
    
    def _extract_client_id(self, request: Request) -> Optional[str]:
        """Extract client ID from request"""
        # Try to get client ID from headers, auth, or IP
        client_id = request.headers.get("X-Client-ID")
        if not client_id:
            client_id = request.headers.get("Authorization", "").split()[-1] if request.headers.get("Authorization") else None
        if not client_id and request.client:
            client_id = request.client.host
        
        return client_id or "anonymous"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting"""
    
    def __init__(self, app, 
                 requests_per_minute: int = 60,
                 tokens_per_minute: int = 10000,
                 burst_allowance: int = 10):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.burst_allowance = burst_allowance
        self.rate_limit_store: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Extract client identifier
            client_id = self._get_client_identifier(request)
            
            # Check rate limits
            is_allowed, limit_info = self._check_rate_limits(client_id, request)
            
            if not is_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests",
                        "retry_after": limit_info.get("retry_after", 60)
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": str(limit_info.get("remaining", 0)),
                        "X-RateLimit-Reset": str(limit_info.get("reset_time", int(time.time()) + 60)),
                        "Retry-After": str(limit_info.get("retry_after", 60))
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(limit_info.get("remaining", self.requests_per_minute))
            response.headers["X-RateLimit-Reset"] = str(limit_info.get("reset_time", int(time.time()) + 60))
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            return await call_next(request)
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Priority: API key > Authorization > Client IP
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key}"
        
        auth_header = request.headers.get("Authorization")
        if auth_header:
            return f"auth:{auth_header.split()[-1] if auth_header.split() else 'unknown'}"
        
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _check_rate_limits(self, client_id: str, request: Request) -> tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limits"""
        current_time = int(time.time())
        window_start = (current_time // 60) * 60  # Round to minute boundary
        
        # Initialize client data if not exists
        if client_id not in self.rate_limit_store:
            self.rate_limit_store[client_id] = {
                "requests": 0,
                "tokens": 0,
                "window_start": window_start,
                "burst_used": 0
            }
        
        client_data = self.rate_limit_store[client_id]
        
        # Reset window if needed
        if client_data["window_start"] < window_start:
            client_data.update({
                "requests": 0,
                "tokens": 0,
                "window_start": window_start,
                "burst_used": 0
            })
        
        # Check request rate limit
        if client_data["requests"] >= self.requests_per_minute:
            # Check if burst allowance available
            if client_data["burst_used"] >= self.burst_allowance:
                return False, {
                    "remaining": 0,
                    "reset_time": window_start + 60,
                    "retry_after": (window_start + 60) - current_time
                }
            else:
                client_data["burst_used"] += 1
        
        # Increment request count
        client_data["requests"] += 1
        
        # Estimate token usage (simplified)
        estimated_tokens = self._estimate_tokens(request)
        
        # Check token rate limit
        if client_data["tokens"] + estimated_tokens > self.tokens_per_minute:
            return False, {
                "remaining": max(0, self.requests_per_minute - client_data["requests"]),
                "reset_time": window_start + 60,
                "retry_after": (window_start + 60) - current_time
            }
        
        client_data["tokens"] += estimated_tokens
        
        return True, {
            "remaining": max(0, self.requests_per_minute - client_data["requests"]),
            "reset_time": window_start + 60,
            "tokens_remaining": max(0, self.tokens_per_minute - client_data["tokens"])
        }
    
    def _estimate_tokens(self, request: Request) -> int:
        """Estimate token usage from request"""
        # Simple estimation based on content length
        # In production, you'd want more sophisticated token counting
        content_length = int(request.headers.get("content-length", "0"))
        return max(1, content_length // 4)  # Rough approximation


class CORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware with version-aware headers"""
    
    def __init__(self, app, 
                 allow_origins: list = None,
                 allow_methods: list = None,
                 allow_headers: list = None):
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allow_headers = allow_headers or [
            "Content-Type", "Authorization", "X-API-Key", "X-Client-ID",
            "Accept", "X-Requested-With", "X-API-Version"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        response.headers["Access-Control-Expose-Headers"] = "X-API-Version, X-Process-Time, X-RateLimit-Remaining"
        
        return response