"""
Legacy API v0.9 - Deprecated
Maintains backward compatibility for legacy clients
"""

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uuid
import time
import logging
import warnings

logger = logging.getLogger(__name__)

v0_9_router = APIRouter()


# Legacy models for v0.9
class LegacyCompletionRequest(BaseModel):
    """Legacy completion request format"""
    prompt: str = Field(..., description="Text prompt")
    max_length: int = Field(100, description="Maximum response length")
    temperature: float = Field(0.7, description="Sampling temperature")
    model: Optional[str] = Field("default", description="Model name")


class LegacyCompletionResponse(BaseModel):
    """Legacy completion response format"""
    id: str = Field(..., description="Completion ID")
    text: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    timestamp: int = Field(..., description="Generation timestamp")


class LegacyErrorResponse(BaseModel):
    """Legacy error response format"""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")


async def add_deprecation_headers(request: Request, response: Response):
    """Add deprecation headers to legacy API responses"""
    
    # Add deprecation warning headers
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Wed, 31 Dec 2024 23:59:59 GMT"
    response.headers["Link"] = '</docs/migration/v0.9-to-v1.0>; rel="deprecation"'
    response.headers["Warning"] = '299 - "API version 0.9 is deprecated. Please migrate to v1.0 or later."'
    
    # Log deprecation usage
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    
    logger.warning(
        f"DEPRECATION: Legacy API v0.9 accessed by {client_ip} "
        f"with User-Agent: {user_agent}. "
        f"Endpoint: {request.url.path}. "
        f"This API will be sunset on 2024-12-31."
    )


@v0_9_router.post("/complete", 
                  response_model=LegacyCompletionResponse,
                  dependencies=[Depends(add_deprecation_headers)])
async def legacy_complete(
    request: LegacyCompletionRequest,
    response: Response
) -> LegacyCompletionResponse:
    """
    Legacy text completion endpoint (DEPRECATED)
    
    This endpoint is deprecated and will be removed on December 31, 2024.
    Please migrate to /v1/completions for continued service.
    """
    
    # Issue deprecation warning
    warnings.warn(
        "API v0.9 is deprecated. Please upgrade to v1.0 or later.",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        # Transform legacy request to modern format
        completion_id = f"legacy-{uuid.uuid4().hex[:12]}"
        
        # Simple mock response in legacy format
        generated_text = f"Legacy response to: {request.prompt[:30]}..."
        
        return LegacyCompletionResponse(
            id=completion_id,
            text=generated_text,
            model=request.model or "legacy-model",
            timestamp=int(time.time())
        )
        
    except Exception as e:
        logger.error(f"Error in legacy completion: {e}")
        raise HTTPException(
            status_code=500,
            detail=LegacyErrorResponse(
                error="Internal server error",
                code="LEGACY_ERROR"
            ).dict()
        )


@v0_9_router.get("/status",
                 dependencies=[Depends(add_deprecation_headers)])
async def legacy_status(response: Response) -> Dict[str, Any]:
    """
    Legacy status endpoint (DEPRECATED)
    
    This endpoint is deprecated. Use /v1/health for health checks.
    """
    
    warnings.warn(
        "API v0.9 status endpoint is deprecated. Use /v1/health instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return {
        "status": "deprecated",
        "message": "This API version is deprecated. Please migrate to v1.0 or later.",
        "migration_guide": "/docs/migration/v0.9-to-v1.0",
        "sunset_date": "2024-12-31",
        "current_time": int(time.time())
    }


@v0_9_router.get("/models",
                 dependencies=[Depends(add_deprecation_headers)])
async def legacy_models(response: Response) -> Dict[str, Any]:
    """
    Legacy models endpoint (DEPRECATED)
    
    This endpoint is deprecated. Use /v1/models for model information.
    """
    
    warnings.warn(
        "API v0.9 models endpoint is deprecated. Use /v1/models instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return {
        "models": [
            {
                "id": "legacy-model",
                "name": "Legacy Text Model",
                "deprecated": True,
                "replacement": "gpt-3.5-turbo"
            }
        ],
        "warning": "This endpoint is deprecated. Please use /v1/models",
        "migration_guide": "/docs/migration/v0.9-to-v1.0"
    }