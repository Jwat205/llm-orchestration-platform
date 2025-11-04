# fastapi-service/app/services/streaming_service.py
import asyncio
from ..models.chat import StreamingDelta
from ..core.ml_engine import ModelManager


async def stream_completion(
    model: str,
    messages: list,
    temperature: float = 1.0,
    max_tokens: int = 100,
    **kwargs
):
    """
    Async generator yielding StreamingDelta objects for SSE.
    Offloads blocking inference to a thread, pushes tokens into an asyncio.Queue.
    """
    manager = ModelManager.get_instance()
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def inference_task():
        # blocking model call, uses callback to push tokens
        def enqueue(token):
            # schedule queue.put in event loop thread
            loop.call_soon_threadsafe(queue.put_nowait, token)

        manager.generate_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            callback=enqueue
        )
        # signal end by enqueuing None
        loop.call_soon_threadsafe(queue.put_nowait, None)

    # start blocking inference in executor
    executor_task = loop.run_in_executor(None, inference_task)

    # yield tokens as they arrive
    while True:
        token = await queue.get()
        if token is None:
            break
        yield StreamingDelta(**token)

    # ensure background thread finishes
    await executor_task