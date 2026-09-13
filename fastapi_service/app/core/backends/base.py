from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.models.chat import ChatCompletionRequest, ChatCompletionResponse


class ModelBackend(ABC):
    """
    Common interface every local-model backend (Transformers, Ollama, ...)
    implements, so the API layer can dispatch to any of them the same way.
    """

    @abstractmethod
    async def generate(self, model_id: str, req: ChatCompletionRequest) -> ChatCompletionResponse:
        ...

    @abstractmethod
    async def generate_stream(self, model_id: str, req: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """Yields incremental text chunks (deltas), not full ChatCompletionChunk objects."""
        ...
