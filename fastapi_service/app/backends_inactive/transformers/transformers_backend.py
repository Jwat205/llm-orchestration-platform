from typing import AsyncGenerator

from app.core.backends.base import ModelBackend
from app.backends_inactive.transformers.ml_engine import ModelManager
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse


class TransformersBackend(ModelBackend):
    """
    Runs models in-process via HuggingFace `transformers`. Good for small
    models the service can keep loaded in its own GPU/CPU memory.

    Currently disconnected from the active model registry while the
    project focuses on the Ollama backend — this module is fully wired
    and importable, just not registered in `model_registry._backends`.
    To reactivate: import and register it in
    `app/core/model_registry.py`.
    """

    async def generate(self, model_id: str, req: ChatCompletionRequest) -> ChatCompletionResponse:
        mgr = ModelManager.for_model(model_id)
        return await mgr.generate_completion(req)

    async def generate_stream(self, model_id: str, req: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        mgr = ModelManager.for_model(model_id)
        async for chunk in mgr.generate_stream(req):
            content = chunk.delta.get("content", "")
            if content:
                yield content
