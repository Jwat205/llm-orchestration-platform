"""
Health check endpoints for API v1
"""

from fastapi import APIRouter
from pydantic import BaseModel
import structlog
import time

router = APIRouter()
logger = structlog.get_logger()

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    service: str = "fastapi-llm-service"
    version: str = "1.0.0"

@router.get("/", response_model=HealthResponse)
async def health_check():
    """Main health check endpoint."""
    logger.info("health_check_requested")

    return HealthResponse(
        status="healthy",
        timestamp=time.time()
    )

@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """Readiness check endpoint."""
    return HealthResponse(
        status="ready",
        timestamp=time.time()
    )

@router.get("/live", response_model=HealthResponse)
async def liveness_check():
    """Liveness check endpoint."""
    return HealthResponse(
        status="alive",
        timestamp=time.time()
    )