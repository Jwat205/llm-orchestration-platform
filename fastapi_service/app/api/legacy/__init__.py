"""
Legacy API Versions
Contains deprecated API versions with deprecation warnings
"""

from fastapi import APIRouter
from .v0_9 import v0_9_router

# Create the main legacy router
legacy_router = APIRouter(prefix="/legacy", tags=["legacy-deprecated"])

# Include legacy versions
legacy_router.include_router(v0_9_router, prefix="/v0.9", tags=["v0.9-deprecated"])

__all__ = ["legacy_router"]