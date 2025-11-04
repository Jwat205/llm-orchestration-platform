# fastapi-service/app/api/v1/chat.py
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from ...models.chat import ChatCompletionRequest, ChatCompletionResponse
from ...api.v1.streaming import event_generator
from ..dependencies import get_current_user, rate_limiter
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/v1/chat", tags=["chat"])

@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limiter)],  # initial request‐level throttle
)
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    stream: bool = False,
    user=Depends(get_current_user),
):
    """
    Combined handler for chat completions:
     - `stream=true`: SSE streaming via event_generator
     - otherwise: standard JSON response
    """
    logger.info("chat.request", user_id=user.user_id, stream=stream, payload=payload.dict())

    if stream:
        return StreamingResponse(
            event_generator(request, payload, user),
            media_type="text/event-stream",
        )

    # non-streaming path
    try:
        #result = await generate_completion(payload)
        result = True  # Placeholder for actual inference logic
        logger.info("chat.response", user_id=user.user_id, result=result.dict())
        return result
    except Exception as e:
        logger.error("chat.error", user_id=user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference failed",
        )
