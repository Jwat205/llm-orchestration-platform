import asyncio
import time
from typing import Optional

import httpx
import structlog

from app.core.ml_engine import ModelManager
from app.core.model_registry import get_backend, resolve_model
from app.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    Usage,
)
from app.services.cache_service import get_cached_response, set_cached_response

logger = structlog.get_logger()

_batch_queue: Optional[asyncio.Queue] = None
_batch_processor_task: Optional[asyncio.Task] = None
BATCH_SIZE = 8
BATCH_TIMEOUT = 0.05


def get_batch_queue() -> asyncio.Queue:
    global _batch_queue
    if _batch_queue is None:
        _batch_queue = asyncio.Queue()
    return _batch_queue


async def start_batch_processor():
    global _batch_processor_task
    _batch_processor_task = asyncio.create_task(_batch_processor_loop())


async def stop_batch_processor():
    global _batch_processor_task
    if _batch_processor_task:
        _batch_processor_task.cancel()
        try:
            await _batch_processor_task
        except asyncio.CancelledError:
            pass


async def _batch_processor_loop():
    mgr = ModelManager()
    while True:
        batch = []
        futures = []
        try:
            req, fut = await asyncio.wait_for(get_batch_queue().get(), timeout=1.0)
            batch.append(req)
            futures.append(fut)
            deadline = time.monotonic() + BATCH_TIMEOUT
            while len(batch) < BATCH_SIZE:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    req2, fut2 = await asyncio.wait_for(get_batch_queue().get(), timeout=remaining)
                    batch.append(req2)
                    futures.append(fut2)
                except asyncio.TimeoutError:
                    break

            loop = asyncio.get_event_loop()
            prompts = [build_prompt(r.messages) for r in batch]
            max_t = max((r.max_tokens or 100) for r in batch)
            temp = batch[0].temperature or 1.0
            texts = await loop.run_in_executor(None, lambda: mgr.generate_batch(prompts, max_t, temp))

            for i, (_, fut_item) in enumerate(zip(batch, futures)):
                if not fut_item.done():
                    result = _build_response(mgr, prompts[i], texts[i])
                    fut_item.set_result(result)

        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("batch_processor.error", error=str(e))
            for fut_item in futures:
                if not fut_item.done():
                    fut_item.set_exception(e)


def _build_response(mgr: ModelManager, prompt: str, text: str) -> ChatCompletionResponse:
    choice = ChatCompletionChoice(
        index=0,
        message={"role": "assistant", "content": text},
        finish_reason="stop",
    )
    usage = Usage(
        prompt_tokens=len(prompt.split()),
        completion_tokens=len(text.split()),
        total_tokens=len(prompt.split()) + len(text.split()),
    )
    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        object="chat.completion",
        created=int(time.time()),
        model=mgr.get_model_name(),
        choices=[choice],
        usage=usage,
    )


def build_prompt(messages) -> str:
    return "\n".join(
        msg.content if hasattr(msg, "content") else msg["content"] for msg in messages
    )


async def generate_completion(req: ChatCompletionRequest) -> ChatCompletionResponse:
    messages_raw = [
        {"role": m.role if hasattr(m, "role") else m["role"],
         "content": m.content if hasattr(m, "content") else m["content"]}
        for m in req.messages
    ]
    cache_key_model = req.model or "default"
    cached = await get_cached_response(
        cache_key_model, messages_raw, req.temperature or 1.0, req.max_tokens or 100
    )
    if cached:
        return ChatCompletionResponse(**cached)

    entry = await resolve_model(cache_key_model)

    if entry.backend == "transformers":
        # Route through the batch processor, which coalesces concurrent
        # requests against the same in-process model for better throughput.
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        await get_batch_queue().put((req, fut))
        result = await fut
    else:
        backend = get_backend(entry.backend)
        result = await backend.generate(entry.model_id, req)

    await set_cached_response(
        cache_key_model, messages_raw, req.temperature or 1.0, req.max_tokens or 100, result.dict()
    )
    return result


async def log_to_billing(user_id: int, model: str, tokens: int):
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://django-service/api/billing/log/",
            json={"user": user_id, "model": model, "tokens": tokens},
        )


async def generate_completion_stream(req: ChatCompletionRequest):
    from app.models.chat import ChatCompletionChunk

    entry = await resolve_model(req.model or "default")
    backend = get_backend(entry.backend)
    stream_id = f"chatcmpl-stream-{int(time.time())}"
    index = 0

    async for delta_text in backend.generate_stream(entry.model_id, req):
        yield ChatCompletionChunk(
            id=stream_id,
            model=entry.model_id,
            index=index,
            delta={"role": "assistant", "content": delta_text},
            finish_reason=None,
        )
        index += 1

    yield ChatCompletionChunk(
        id=stream_id,
        model=entry.model_id,
        index=index,
        delta={},
        finish_reason="stop",
    )
