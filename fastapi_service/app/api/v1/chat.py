# fastapi-service/app/api/v1/chat.py

import structlog
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.chat import ChatCompletionRequest , ChatCompletionResponse, ChatCompletionChunk
from ...services.inference_service import generate_completion
from ...api.v1.streaming import event_generator
from ..dependencies import authenticate_user, check_rate_limit

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["chat"])

# Add a simple health check endpoint
@router.get("/health")
async def chat_health():
    """Simple health check for chat service"""
    return {"status": "healthy", "service": "chat"}

# Development endpoint without authentication
@router.post("/dev/completions", response_model=ChatCompletionResponse)
async def dev_chat_completions(request: Request, payload: ChatCompletionRequest):
    """
    Development chat completion endpoint without authentication.
    For frontend development and testing only.
    """
    from app.config import settings

    if settings.ENV != "development":
        raise HTTPException(status_code=404, detail="Endpoint not available in production")

    logger.info("dev.chat.request", model=payload.model, stream=False)

    try:
        result = await generate_completion(payload)
        logger.info("dev.chat.response", result=result)
        return result
    except Exception as exc:
        logger.error("dev.chat.error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference error",
        )

@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    dependencies=[Depends(authenticate_user), Depends(check_rate_limit)],
    status_code=status.HTTP_200_OK,
)
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    stream: bool = False,
    user=Depends(authenticate_user),
):
    """
    OpenAI-compatible chat completion endpoint.
    - If `?stream=true`, returns an SSE stream of ChatCompletionChunk events.
    - Otherwise returns full ChatCompletionResponse JSON.
    """
    logger.info("chat.request", user_id=user.user_id, model=payload.model, stream=stream)

    if stream:
        # Server-Sent Events branch
        print("Streaming enabled")
        return StreamingResponse(
            event_generator(request, payload, user),
            media_type="text/event-stream",
        )

    # Non-streaming (standard) branch
    try:
        result = await generate_completion(payload)
        logger.info("chat.response", user_id=user.user_id, result=result)
        return result

    except HTTPException:
        # Propagate any HTTPExceptions (e.g. 401, 429) untouched
        raise

    except Exception as exc:
        logger.error("chat.error", user_id=user.user_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference error",
        )
