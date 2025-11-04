# fastapi-service/app/api/v1/streaming.py
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from structlog import get_logger
from ...models.chat import ChatCompletionRequest, ChatCompletionChunk
from ...services.inference_service import generate_completion_stream
from app.api.dependencies import log_usage, check_rate_limit

logger = get_logger()

async def event_generator(
    request: Request,
    payload: ChatCompletionRequest,
    user
) -> AsyncGenerator[bytes, None]:
    """
    SSE generator yielding token chunks for chat completions.
    """
    # 1) Tell clients how long to wait before reconnect attempts
    yield b"retry: 1000\n\n"
    logger.info("stream.start", user_id=user.user_id, model=payload.model)
    token_count = 0

    # 2) Stream tokens one by one
    async for chunk in generate_completion_stream(payload):
        # 3) If client dropped, abort
        if await request.is_disconnected():
            logger.info("stream.disconnect", user_id=user.user_id)
            break

        # 4) Per‐token throttling (you can tweak this)
        try:
            await check_rate_limit(user)
        except HTTPException:
            logger.warning("stream.rate_limited", user_id=user.user_id)
            yield b"data: [ERROR: rate limit exceeded]\n\n"
            break

        token_count += 1
        # 5) Log usage back to Django
        await log_usage({
            "user_id": user.user_id,
            "model": payload.model,
            "tokens": 1,
        })

        # 6) Wrap in SSE “data:” framing
        sse_chunk = b"data: " + chunk.json().encode() + b"\n\n"
        logger.info(
            "stream.chunk_sent",
            user_id=user.user_id,
            token_count=token_count,
            chunk=chunk.dict(),
        )
        yield sse_chunk

    # 7) Signal end of stream
    yield b"data: [DONE]\n\n"
    logger.info("stream.end", user_id=user.user_id, total_tokens=token_count)
