from fastapi import APIRouter
from .endpoints import embeddings, monitoring, health
from .chat import router as chat_router
from .models import router as models_router

v1_router = APIRouter(prefix="/v1", tags=["v1"])

# Primary OpenAI-compatible endpoint (auth + batching + caching)
v1_router.include_router(chat_router)

# Model picker: list local models available across all backends
v1_router.include_router(models_router)

# Supporting endpoints
v1_router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings-v1"])
v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring-v1"])
v1_router.include_router(health.router, prefix="/health", tags=["health-v1"])

__all__ = ["v1_router"]
