import json
import time
from typing import AsyncGenerator, List

import httpx
import structlog

from app.config import settings
from app.core.backends.base import ModelBackend
from app.models.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    Usage,
)

logger = structlog.get_logger()


def _to_ollama_messages(messages: List[Message]) -> list:
    return [{"role": m.role, "content": m.content} for m in messages]


class OllamaBackend(ModelBackend):
    """
    Runs models via a local Ollama server (http://localhost:11434 by default).
    Ollama handles model loading/unloading and quantization, so this is just
    a thin HTTP client — no GPU management code needed here.
    """

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.ollama_base_url

    async def generate(self, model_id: str, req: ChatCompletionRequest) -> ChatCompletionResponse:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            resp = await client.post(
                "/api/chat",
                json={
                    "model": model_id,
                    "messages": _to_ollama_messages(req.messages),
                    "stream": False,
                    "options": {
                        "temperature": req.temperature,
                        "top_p": req.top_p,
                        "num_predict": req.max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatCompletionResponse(
            id=f"ollama-{int(time.time())}",
            model=model_id,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message={"role": "assistant", "content": content},
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def generate_stream(self, model_id: str, req: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": model_id,
                    "messages": _to_ollama_messages(req.messages),
                    "stream": True,
                    "options": {
                        "temperature": req.temperature,
                        "top_p": req.top_p,
                        "num_predict": req.max_tokens,
                    },
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break

    async def list_models(self) -> List[str]:
        """Models currently pulled/available on the Ollama server."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=10) as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            logger.warning("ollama.list_models_error", error=str(e))
            return []
