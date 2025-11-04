"""
API Version 1.0 - Current Stable Version
This module contains the stable v1 API endpoints and handlers
"""

from fastapi import APIRouter
from .endpoints import llm_endpoints, embeddings, monitoring, health

# Create the main v1 router
v1_router = APIRouter(prefix="/v1", tags=["v1"])

# Include all v1 endpoints
v1_router.include_router(llm_endpoints.router, prefix="/llm", tags=["llm-v1"])
v1_router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings-v1"])
v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring-v1"])
v1_router.include_router(health.router, prefix="/health", tags=["health-v1"])

__all__ = ["v1_router"]