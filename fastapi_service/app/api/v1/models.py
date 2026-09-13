# fastapi-service/app/api/v1/models.py

from fastapi import APIRouter, Depends

from app.core.model_registry import list_models
from ..dependencies import authenticate_user

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def get_models(user=Depends(authenticate_user)):
    """
    List local models available to pick from. Includes statically
    registered in-process (transformers) models plus whatever is currently
    pulled on the Ollama server.
    """
    entries = await list_models()
    return {
        "data": [
            {
                "id": entry.name,
                "backend": entry.backend,
                "label": entry.label or entry.name,
            }
            for entry in entries
        ]
    }
