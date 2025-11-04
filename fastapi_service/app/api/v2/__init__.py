"""
API Version 2.0 - Beta Version
This module contains the next generation v2 API endpoints with enhanced features
"""

from fastapi import APIRouter
from .endpoints import llm_endpoints, analytics, batch_processing, advanced_monitoring

# Create the main v2 router
v2_router = APIRouter(prefix="/v2", tags=["v2-beta"])

# Include all v2 endpoints
v2_router.include_router(llm_endpoints.router, prefix="/llm", tags=["llm-v2"])
v2_router.include_router(analytics.router, prefix="/analytics", tags=["analytics-v2"])
v2_router.include_router(batch_processing.router, prefix="/batch", tags=["batch-v2"])
v2_router.include_router(advanced_monitoring.router, prefix="/monitoring", tags=["monitoring-v2"])

__all__ = ["v2_router"]