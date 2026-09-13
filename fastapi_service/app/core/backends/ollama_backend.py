import asyncio
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
    Runs models via one or more local Ollama servers. Ollama handles model
    loading/unloading and quantization; this is a thin HTTP client that also
    load-balances across multiple Ollama instances (see `OLLAMA_BASE_URLS`)
    since a single Ollama process serializes generation requests, one at a
    time, regardless of how many clients are connected.

    Routing is "least in-flight requests" rather than round-robin, so a slow
    instance naturally receives fewer new requests instead of queuing behind
    it blindly.
    """

    def __init__(self, base_url: str = None, base_urls: List[str] = None):
        if base_urls:
            self.base_urls = base_urls
        elif settings.ollama_base_urls:
            self.base_urls = [u.strip() for u in settings.ollama_base_urls.split(",") if u.strip()]
        else:
            self.base_urls = [base_url or settings.ollama_base_url]
        self._in_flight = {url: 0 for url in self.base_urls}
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Back-compat single-URL accessor (first configured instance)."""
        return self.base_urls[0]

    async def _pick_instance(self) -> str:
        async with self._lock:
            url = min(self._in_flight, key=self._in_flight.get)
            self._in_flight[url] += 1
            return url

    async def _release_instance(self, url: str):
        async with self._lock:
            self._in_flight[url] -= 1

    async def generate(self, model_id: str, req: ChatCompletionRequest) -> ChatCompletionResponse:
        url = await self._pick_instance()
        try:
            async with httpx.AsyncClient(base_url=url, timeout=120) as client:
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
        finally:
            await self._release_instance(url)

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatCompletionResponse(
            id=f"ollama-{int(time.time())}",
            created=int(time.time()),
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
        url = await self._pick_instance()
        try:
            async with httpx.AsyncClient(base_url=url, timeout=120) as client:
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
        finally:
            await self._release_instance(url)

    async def list_models(self) -> List[str]:
        """Models currently pulled/available on the Ollama server(s)."""
        try:
            async with httpx.AsyncClient(base_url=self.base_urls[0], timeout=10) as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            logger.warning("ollama.list_models_error", error=str(e))
            return []
